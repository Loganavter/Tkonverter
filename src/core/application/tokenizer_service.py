

import importlib.util
import json
import os
import subprocess
import sys
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.resources.translations import tr

_SUBPROCESS_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0

def _is_frozen_windows() -> bool:
    return getattr(sys, "frozen", False) is True and sys.platform == "win32"

def _get_frozen_helper_script_path() -> Optional[str]:
    if not _is_frozen_windows():
        return None
    try:
        root = getattr(sys, "_MEIPASS", None)
        if not root:
            return None
        path = os.path.join(root, "src", "core", "tokenizer_helper.py")
        return path if os.path.isfile(path) else None
    except Exception:
        return None

def _get_frozen_venv_python() -> Optional[str]:
    if not _is_frozen_windows():
        return None
    try:
        from src.core.flatpak_tokenizer_path import (
            get_frozen_windows_venv_python,
            is_frozen_windows,
        )
        if not is_frozen_windows():
            return None
        p = get_frozen_windows_venv_python()
        return str(p) if p and p.exists() else None
    except Exception:
        return None

def _run_frozen_helper(
    model: str,
    count_text: Optional[str] = None,
    info: bool = False,
    allow_download: bool = False,
    hf_token: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Run tokenizer_helper.py in the venv. allow_download=True lets it fetch from Hugging Face."""
    venv_python = _get_frozen_venv_python()
    script = _get_frozen_helper_script_path()
    if not venv_python or not script:
        return subprocess.CompletedProcess([], -1, stdout="", stderr="no venv or script")
    cmd = [venv_python, script, "--model", model]
    if info:
        cmd.append("--info")
    elif count_text is not None:
        cmd.append("--count")
    else:
        cmd.append("--check")
    if allow_download:
        cmd.append("--download")
    env = dict(os.environ)
    token_str = (hf_token or "").strip()
    if token_str:
        env["HF_TOKEN"] = token_str
        env["HUGGING_FACE_HUB_TOKEN"] = token_str
    if not allow_download:
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
    return subprocess.run(
        cmd,
        input=count_text if count_text is not None else None,
        capture_output=True,
        text=True,
        timeout=300 if allow_download else 120,
        creationflags=_SUBPROCESS_FLAGS,
        env=env,
    )

def _start_frozen_daemon(
    model: str,
    allow_download: bool = False,
    hf_token: Optional[str] = None,
) -> Optional[Tuple[subprocess.Popen, Any, Any]]:
    """Start long-lived tokenizer helper process (--daemon). Returns (process, stdin, stdout) or None."""
    venv_python = _get_frozen_venv_python()
    script = _get_frozen_helper_script_path()
    if not venv_python or not script:
        return None
    cmd = [venv_python, script, "--model", model, "--daemon"]
    if allow_download:
        cmd.append("--download")
    env = dict(os.environ)
    token_str = (hf_token or "").strip()
    if token_str:
        env["HF_TOKEN"] = token_str
        env["HUGGING_FACE_HUB_TOKEN"] = token_str
    if not allow_download:
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
            creationflags=_SUBPROCESS_FLAGS,
        )
        return (proc, proc.stdin, proc.stdout)
    except Exception:
        return None

def _transformers_available() -> bool:
    if _is_frozen_windows():
        venv_python = _get_frozen_venv_python()
        if not venv_python:
            return False
        r = subprocess.run(
            [venv_python, "-c", "import transformers"],
            capture_output=True,
            timeout=10,
            creationflags=_SUBPROCESS_FLAGS,
        )
        return r.returncode == 0
    return importlib.util.find_spec("transformers") is not None

class TokenizerError(Exception):

    pass

class _FrozenTokenizerProxy:

    def __init__(
        self,
        model_name: str,
        process: Optional[subprocess.Popen] = None,
        stdin_w: Optional[Any] = None,
        stdout_r: Optional[Any] = None,
    ):
        self._model_name = model_name
        self._process = process
        self._stdin_w = stdin_w
        self._stdout_r = stdout_r
        self._lock = threading.Lock()
        self.vocab_size = None
        self.model_max_length = None

    def _encode_via_daemon(self, text: str) -> int:
        if not self._stdin_w or not self._stdout_r or not self._process or self._process.poll() is not None:
            raise TokenizerError("Tokenizer daemon not running")
        with self._lock:
            try:
                self._stdin_w.write(json.dumps({"action": "count", "text": text}) + "\n")
                self._stdin_w.flush()
                line = self._stdout_r.readline()
            except (BrokenPipeError, OSError, ValueError) as e:
                raise TokenizerError(f"Daemon communication error: {e}")
        if not line:
            raise TokenizerError("Tokenizer daemon closed connection")
        try:
            out = json.loads(line.strip())
        except json.JSONDecodeError:
            raise TokenizerError("Invalid response from tokenizer daemon")
        if not out.get("ok"):
            raise TokenizerError(out.get("error", "Unknown daemon error"))
        return int(out.get("count", 0))

    def encode(self, text: str) -> List[int]:
        if self._process is not None and self._stdin_w and self._stdout_r:
            n = self._encode_via_daemon(text)
            return [0] * n
        r = _run_frozen_helper(self._model_name, count_text=text)
        if r.returncode != 0:
            raise TokenizerError(r.stderr or "Tokenizer subprocess failed")
        try:
            n = int(r.stdout.strip())
            return [0] * n
        except ValueError:
            raise TokenizerError("Invalid token count from helper")

    def shutdown(self) -> None:
        if not self._process or not self._stdin_w:
            return
        try:
            self._stdin_w.write(json.dumps({"action": "quit"}) + "\n")
            self._stdin_w.flush()
        except (BrokenPipeError, OSError):
            pass
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
        try:
            self._stdin_w.close()
        except OSError:
            pass
        self._process = None
        self._stdin_w = None
        self._stdout_r = None

class TokenizerService:

    def __init__(self):
        self._current_tokenizer: Optional[Any] = None
        self._current_model_name: Optional[str] = None
        self._default_model = "google/gemma-2b"

    def is_transformers_available(self) -> bool:
        return _transformers_available()

    def load_tokenizer(
        self,
        model_name: str,
        local_only: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None,
        hf_token: Optional[str] = None,
    ) -> Any:
        if not _transformers_available():
            raise TokenizerError("Transformers library is not installed")

        if _is_frozen_windows():
            if progress_callback:
                progress_callback(f"Loading tokenizer {model_name}...")
            r = _run_frozen_helper(
                model_name,
                allow_download=not local_only,
                hf_token=hf_token,
            )
            if r.returncode != 0:
                err = (r.stderr or "").strip()
                if "gated" in err.lower() or "401" in err or "authenticated" in err.lower() or "access to model" in err.lower():
                    raise TokenizerError(
                        tr("install.gated_model_error", model=model_name)
                    )
                raise TokenizerError(
                    err or "Failed to load tokenizer. "
                    "Try removing %LOCALAPPDATA%\\Tkonverter\\tokenizer_venv and reinstalling."
                )
            self._current_model_name = model_name
            allow_download = not local_only
            daemon = _start_frozen_daemon(model_name, allow_download=allow_download, hf_token=hf_token)
            if daemon is None:
                raise TokenizerError("Failed to start tokenizer daemon")
            proc, stdin_w, stdout_r = daemon
            if proc.poll() is not None:
                raise TokenizerError("Tokenizer daemon exited during startup")
            proxy = _FrozenTokenizerProxy(model_name, process=proc, stdin_w=stdin_w, stdout_r=stdout_r)
            try:
                stdin_w.write(json.dumps({"action": "info"}) + "\n")
                stdin_w.flush()
                line = stdout_r.readline()
                if line:
                    out = json.loads(line.strip())
                    if out.get("ok"):
                        proxy.vocab_size = out.get("vocab_size")
                        proxy.model_max_length = out.get("model_max_length")
            except Exception:
                pass
            if proc.poll() is not None:
                proxy.shutdown()
                raise TokenizerError("Tokenizer daemon exited after load")
            self._current_tokenizer = proxy
            if progress_callback:
                progress_callback(f"Tokenizer {model_name} loaded successfully")
            return proxy

        try:
            if progress_callback:
                progress_callback(f"Loading tokenizer {model_name}...")

            from transformers import AutoTokenizer

            token_str = (hf_token or "").strip() or None
            if local_only:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_name,
                    local_files_only=True,
                    token=token_str,
                )
            else:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_name,
                    token=token_str,
                )

            self._current_tokenizer = tokenizer
            self._current_model_name = model_name

            if progress_callback:
                progress_callback(f"Tokenizer {model_name} loaded successfully")

            return tokenizer

        except OSError as e:
            if "not found" in str(e).lower():
                raise TokenizerError(f"Model {model_name} not found in local cache")
            else:
                raise TokenizerError(f"Error loading tokenizer: {e}")
        except ImportError as e:
            raise TokenizerError(
                f"Transformers import failed: {e}. "
                "Try removing %LOCALAPPDATA%\\Tkonverter\\tokenizer_venv and reinstalling the tokenizer."
            )
        except Exception as e:
            raise TokenizerError(f"Unexpected error: {e}")

    def load_default_tokenizer(
        self, progress_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[Any]:
        if not _transformers_available():
            if progress_callback:
                progress_callback("Transformers library not found")
            return None

        cache_info = self.check_model_cache(self._default_model)
        if not cache_info.get("available", False):
            if progress_callback:
                progress_callback(f"Model {self._default_model} not found in cache")
            return None

        try:
            return self.load_tokenizer(
                self._default_model,
                local_only=True,
                progress_callback=progress_callback,
            )
        except TokenizerError as e:
            if progress_callback:
                progress_callback(f"Failed to load tokenizer from cache: {e}")
            return None

    def get_current_tokenizer(self) -> Optional[Any]:
        return self._current_tokenizer

    def get_current_model_name(self) -> Optional[str]:
        return self._current_model_name

    def has_tokenizer_loaded(self) -> bool:
        return self._current_tokenizer is not None

    def is_tokenizer_loaded(self) -> bool:
        return self.has_tokenizer_loaded()

    def unload_tokenizer(self):
        if isinstance(self._current_tokenizer, _FrozenTokenizerProxy):
            self._current_tokenizer.shutdown()
        self._current_tokenizer = None
        self._current_model_name = None

    def get_tokenizer_info(self) -> Dict[str, Any]:
        if not self._current_tokenizer:
            return {
                "loaded": False,
                "model_name": None,
                "vocab_size": None,
                "model_max_length": None,
            }

        try:
            vocab_size = getattr(self._current_tokenizer, "vocab_size", None)
            model_max_length = getattr(
                self._current_tokenizer, "model_max_length", None
            )
            return {
                "loaded": True,
                "model_name": self._current_model_name,
                "vocab_size": vocab_size,
                "model_max_length": model_max_length,
            }
        except Exception as e:
            return {
                "loaded": True,
                "model_name": self._current_model_name,
                "vocab_size": None,
                "model_max_length": None,
                "error": str(e),
            }

    def tokenize_text(
        self,
        text: str,
        anonymizer_enabled: bool = False,
        anonymizer_service: Optional[Any] = None,
    ) -> int:
        if not self._current_tokenizer:
            raise TokenizerError("Tokenizer not loaded")

        try:
            text_to_tokenize = text
            if anonymizer_enabled and anonymizer_service is not None:
                text_to_tokenize = anonymizer_service.anonymize_text(text)

            tokens = self._current_tokenizer.encode(text_to_tokenize)
            return len(tokens)
        except Exception as e:
            raise TokenizerError(f"Tokenization error: {e}")

    def get_available_models(self) -> list[str]:
        return [
            "google/gemma-2b",
            "microsoft/DialoGPT-medium",
            "openai-gpt",
            "gpt2",
            "facebook/opt-125m",
            "EleutherAI/gpt-neo-125M",
        ]

    def get_default_model_name(self) -> str:
        return self._default_model

    def set_default_model(self, model_name: str):
        self._default_model = model_name

    def check_model_cache(self, model_name: str) -> Dict[str, Any]:
        if not _transformers_available():
            return {"available": False, "reason": "transformers not installed"}

        if _is_frozen_windows():
            r = _run_frozen_helper(model_name)
            if r.returncode == 0:
                return {"available": True, "model_name": model_name, "vocab_size": None}
            return {"available": False, "reason": r.stderr or "not in cache"}

        try:
            from transformers import AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                model_name, local_files_only=True
            )
            return {
                "available": True,
                "model_name": model_name,
                "vocab_size": getattr(tokenizer, "vocab_size", None),
            }
        except OSError:
            return {"available": False, "reason": "not in cache"}
        except Exception as e:
            return {"available": False, "reason": f"error: {e}"}

    def clear_cache_info(self, model_name: str) -> Dict[str, Any]:
        if _is_frozen_windows():
            return {
                "found": False,
                "error": "Remove cache manually: %LOCALAPPDATA%\\Tkonverter\\hf_cache",
            }

        try:
            from huggingface_hub import scan_cache_dir

            hf_cache_info = scan_cache_dir()
            repo_info = next(
                (repo for repo in hf_cache_info.repos if repo.repo_id == model_name),
                None,
            )
            if not repo_info:
                return {"found": False, "message": "Model not found in cache"}
            revisions_to_delete = {rev.commit_hash for rev in repo_info.revisions}
            delete_strategy = hf_cache_info.delete_revisions(*revisions_to_delete)
            return {
                "found": True,
                "model_name": model_name,
                "size_to_free": delete_strategy.expected_freed_size_str,
                "revisions_count": len(revisions_to_delete),
            }
        except ImportError:
            return {"found": False, "error": "huggingface_hub not installed"}
        except Exception as e:
            return {"found": False, "error": str(e)}
