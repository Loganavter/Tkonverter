import logging
import subprocess
import sys
import threading
from typing import Any, Dict, Optional, Set

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

_SUBPROCESS_FLAGS = (
    getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
)

from core.analysis.tree_analyzer import TreeNode
from core.application.analysis_service import AnalysisService
from core.application.chat_service import ChatLoadError, ChatService
from core.application.conversion_service import ConversionService
from core.application.tokenizer_service import TokenizerError, TokenizerService
from core.domain.models import AnalysisResult, Chat
from src.resources.translations import tr

logger = logging.getLogger(__name__)

class WorkerSignals(QObject):

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, object)

class ChatLoadSignals(QObject):

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, object, str)

class AIInstallerSignals(QObject):

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

class ChatLoadWorker(QRunnable):

    def __init__(self, chat_service: ChatService, file_path: str):
        super().__init__()
        self.chat_service = chat_service
        self.file_path = file_path
        self.signals = ChatLoadSignals()

    def run(self):
        status_callback = lambda msg: self.signals.progress.emit(msg)
        error_callback = lambda msg: self.signals.progress.emit(msg)
        self.chat_service.add_status_listener(status_callback)
        self.chat_service.add_error_listener(error_callback)
        try:
            chat = self.chat_service.load_chat_from_file(self.file_path)
            self.signals.finished.emit(True, tr("status.file_loaded"), chat, self.file_path)
        except ChatLoadError as e:
            logger.warning(f"Chat load error for '{self.file_path}': {e}")
            self.signals.finished.emit(False, str(e), None, "")
        except Exception as e:
            logger.exception(f"Unexpected error loading chat '{self.file_path}': {e}")
            self.signals.finished.emit(
                False, tr("common.unexpected_error", error=str(e)), None, ""
            )
        finally:
            self.chat_service.remove_status_listener(status_callback)
            self.chat_service.remove_error_listener(error_callback)

class ConversionWorker(QRunnable):

    def __init__(
        self,
        conversion_service: ConversionService,
        chat: Chat,
        config: Dict[str, Any],
        save_path: str,
        disabled_nodes: Optional[Set[TreeNode]] = None,
    ):
        super().__init__()
        self.conversion_service = conversion_service
        self.chat = chat
        self.config = config
        self.save_path = save_path
        self.disabled_nodes = disabled_nodes or set()
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.progress.emit(tr("status.converting"))
            text = self.conversion_service.convert_to_text(
                self.chat,
                self.config,
                html_mode=False,
                disabled_nodes=self.disabled_nodes,
            )

            with open(self.save_path, "w", encoding="utf-8") as f:
                f.write(text)

            self.signals.finished.emit(True, self.save_path, None)
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            self.signals.finished.emit(False, str(e), None)

class AnalysisWorker(QRunnable):

    def __init__(
        self,
        analysis_service: AnalysisService,
        chat: Chat,
        config: Dict[str, Any],
        tokenizer: Optional[Any] = None,
        disabled_dates: Optional[Set[Any]] = None,
    ):
        super().__init__()
        self.analysis_service = analysis_service
        self.chat = chat
        self.config = config
        self.tokenizer = tokenizer
        self.disabled_dates = disabled_dates or set()
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            self._is_cancelled = True

    def is_cancelled(self):
        with self._lock:
            return self._is_cancelled

    def run(self):
        try:
            status_callback = lambda msg: self.signals.progress.emit(msg)
            error_callback = lambda msg: self.signals.progress.emit(msg)
            self.analysis_service.add_status_listener(status_callback)
            self.analysis_service.add_error_listener(error_callback)
            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            if self.tokenizer:
                result = self.analysis_service.calculate_token_stats(
                    self.chat,
                    self.config,
                    self.tokenizer,
                    disabled_dates=set(),
                    include_memory_disabled_dates=False,
                )
            else:
                result = self.analysis_service.calculate_character_stats(
                    self.chat,
                    self.config,
                    disabled_dates=set(),
                    include_memory_disabled_dates=False,
                )

            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            self.signals.finished.emit(True, tr("status.analysis_completed"), result)
        except Exception as e:
            if not self.is_cancelled():
                logger.exception(f"Analysis error: {e}")
                self.signals.finished.emit(False, str(e), None)
        finally:
            self.analysis_service.remove_status_listener(status_callback)
            self.analysis_service.remove_error_listener(error_callback)

class TreeBuildWorker(QRunnable):

    def __init__(
        self,
        analysis_service: AnalysisService,
        analysis_result: AnalysisResult,
        config: Dict[str, Any],
    ):
        super().__init__()
        self.analysis_service = analysis_service
        self.analysis_result = analysis_result
        self.config = config
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            self._is_cancelled = True

    def is_cancelled(self):
        with self._lock:
            return self._is_cancelled

    def run(self):
        try:
            self.signals.progress.emit(tr("status.building_tree"))

            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            tree = self.analysis_service.build_analysis_tree(
                self.analysis_result, self.config
            )

            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            self.signals.finished.emit(True, tr("status.tree_built"), tree)
        except Exception as e:
            if not self.is_cancelled():
                logger.error(f"Tree building error: {e}")
                self.signals.finished.emit(False, str(e), None)

class TokenizerLoadWorker(QRunnable):

    def __init__(
        self,
        tokenizer_service: TokenizerService,
        model_name: str,
        hf_token: Optional[str] = None,
    ):
        super().__init__()
        self.tokenizer_service = tokenizer_service
        self.model_name = model_name
        self.hf_token = (hf_token or "").strip() or None
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            self._is_cancelled = True

    def is_cancelled(self):
        with self._lock:
            return self._is_cancelled

    def run(self):
        try:

            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            progress_callback = lambda msg: self.signals.progress.emit(msg)
            tokenizer = self.tokenizer_service.load_tokenizer(
                self.model_name,
                local_only=False,
                progress_callback=progress_callback,
                hf_token=self.hf_token,
            )

            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            self.signals.finished.emit(
                True, tr("install.tokenizer_loaded"), tokenizer
            )
        except TokenizerError as e:
            if not self.is_cancelled():
                self.signals.finished.emit(False, str(e), None)
        except Exception as e:
            if not self.is_cancelled():
                logger.error(f"Unexpected tokenizer error: {e}")
                self.signals.finished.emit(False, str(e), None)

class AIInstallerWorker(QRunnable):

    def __init__(self, action: str, model_name: str | None = None):
        super().__init__()
        self.signals = AIInstallerSignals()
        self.action = action
        self.model_name = model_name

    def run(self):
        if self.action == "install_deps":
            self._install_dependencies()
        elif self.action == "remove_model":
            self._remove_model_cache()

    def _remove_model_cache(self):
        if not self.model_name:
            self.signals.finished.emit(False, tr("install.model_name_required"))
            return

        try:
            from huggingface_hub import scan_cache_dir
        except ImportError:
            self.signals.finished.emit(False, tr("install.huggingface_not_installed"))
            return

        try:
            self.signals.progress.emit(tr("install.scanning_cache"))
            hf_cache_info = scan_cache_dir()

            repo_info = next(
                (
                    repo
                    for repo in hf_cache_info.repos
                    if repo.repo_id == self.model_name
                ),
                None,
            )

            if not repo_info:
                self.signals.progress.emit(tr("install.model_not_in_cache"))
                self.signals.finished.emit(
                    True, tr("install.cache_removed")
                )
                return

            self.signals.progress.emit(tr("install.found_model_deleting"))
            revisions_to_delete = {rev.commit_hash for rev in repo_info.revisions}

            delete_strategy = hf_cache_info.delete_revisions(*revisions_to_delete)
            self.signals.progress.emit(
                tr("install.will_free",
                    size=delete_strategy.expected_freed_size_str
                )
            )
            self.signals.progress.emit(tr("install.deleting_model"))
            delete_strategy.execute()

            self.signals.finished.emit(True, tr("install.cache_removed"))
        except Exception as e:
            self.signals.finished.emit(False, str(e))

    def _install_dependencies(self):

        packages = ["transformers[sentencepiece]", "huggingface_hub"]

        try:
            from src.core.flatpak_tokenizer_path import (
                get_flatpak_venv_python,
                get_flatpak_venv_root,
                is_flatpak,
                is_frozen_windows,
                get_frozen_windows_venv_root,
                get_frozen_windows_venv_python,
                get_frozen_windows_system_python,
                ensure_frozen_windows_tokenizer_path,
            )
        except ImportError:
            pass
        else:
            if is_flatpak():
                self._install_dependencies_flatpak(packages)
                return
            if is_frozen_windows():
                self._install_dependencies_frozen_windows(
                    packages,
                    get_frozen_windows_venv_root,
                    get_frozen_windows_venv_python,
                    get_frozen_windows_system_python,
                    ensure_frozen_windows_tokenizer_path,
                )
                return
        if sys.prefix == sys.base_prefix:
            error_msg = tr("install.refusing_system_python")
            self.signals.progress.emit(f"ERROR: {error_msg}")
            self.signals.finished.emit(False, error_msg)
            return
        command = [sys.executable, "-m", "pip", "install", "--upgrade", *packages]
        try:
            self.signals.progress.emit(
                tr("install.executing", command=" ".join(command))
            )
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_SUBPROCESS_FLAGS,
            )

            for line in iter(process.stdout.readline, ""):
                self.signals.progress.emit(line.strip())

            process.wait()

            if process.returncode == 0:
                self.signals.finished.emit(True, tr("install.operation_ok"))
            else:
                self.signals.finished.emit(
                    False,
                    tr("install.operation_failed", code=process.returncode),
                )
        except Exception as e:
            self.signals.finished.emit(False, str(e))

    def _install_dependencies_frozen_windows(
        self,
        packages: list,
        get_venv_root,
        get_venv_python,
        get_system_python,
        ensure_tokenizer_path,
    ):
        venv_root = get_venv_root()
        if not venv_root:
            self.signals.finished.emit(
                False,
                "Could not determine tokenizer venv path (LOCALAPPDATA).",
            )
            return
        venv_root.mkdir(parents=True, exist_ok=True)

        scripts_dir = venv_root / "Scripts"
        if not scripts_dir.exists() or not (scripts_dir / "python.exe").exists():
            self.signals.progress.emit("Finding Python to create tokenizer environment...")
            system_python = get_system_python()
            if not system_python:
                self.signals.finished.emit(
                    False,
                    "No Python found. Install Python from python.org or Microsoft Store and add it to PATH.",
                )
                return
            self.signals.progress.emit("Creating virtual environment...")
            create = subprocess.run(
                [system_python, "-m", "venv", str(venv_root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_SUBPROCESS_FLAGS,
            )
            if create.returncode != 0:
                err = create.stderr or create.stdout or "unknown"
                self.signals.finished.emit(False, f"Failed to create venv: {err}")
                return

        venv_python = get_venv_python()
        if not venv_python or not venv_python.exists():
            self.signals.finished.emit(
                False,
                "Tokenizer venv Python not found after creation.",
            )
            return

        command = [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            *packages,
        ]
        try:
            self.signals.progress.emit(
                tr("install.executing", command=" ".join(command))
            )
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_SUBPROCESS_FLAGS,
            )
            for line in iter(process.stdout.readline, ""):
                self.signals.progress.emit(line.strip())
            process.wait()
            if process.returncode == 0:
                ensure_tokenizer_path()
                self.signals.finished.emit(True, tr("install.operation_ok"))
            else:
                self.signals.finished.emit(
                    False,
                    tr("install.operation_failed", code=process.returncode),
                )
        except Exception as e:
            self.signals.finished.emit(False, str(e))

    def _install_dependencies_flatpak(self, packages: list):
        from src.core.flatpak_tokenizer_path import (
            get_flatpak_venv_python,
            get_flatpak_venv_root,
        )

        venv_root = get_flatpak_venv_root()
        if not venv_root:
            self.signals.finished.emit(
                False,
                "Flatpak: could not determine data directory (XDG_DATA_HOME).",
            )
            return
        venv_root.mkdir(parents=True, exist_ok=True)

        if not (venv_root / "bin").exists() and not (venv_root / "Scripts").exists():
            self.signals.progress.emit("Creating virtual environment...")
            create = subprocess.run(
                [sys.executable, "-m", "venv", str(venv_root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_SUBPROCESS_FLAGS,
            )
            if create.returncode != 0:
                err = create.stderr or create.stdout or "unknown"
                self.signals.finished.emit(
                    False,
                    f"Failed to create venv: {err}",
                )
                return

        venv_python = get_flatpak_venv_python()
        if not venv_python or not venv_python.exists():
            self.signals.finished.emit(
                False,
                "Flatpak: venv Python not found after creation.",
            )
            return

        command = [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            *packages,
        ]
        try:
            self.signals.progress.emit(
                tr("install.executing", command=" ".join(command))
            )
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_SUBPROCESS_FLAGS,
            )
            for line in iter(process.stdout.readline, ""):
                self.signals.progress.emit(line.strip())
            process.wait()
            if process.returncode == 0:
                self.signals.finished.emit(True, tr("install.operation_ok"))
            else:
                self.signals.finished.emit(
                    False,
                    tr("install.operation_failed", code=process.returncode),
                )
        except Exception as e:
            self.signals.finished.emit(False, str(e))

def sync_load_tokenizer(
    tokenizer_service: TokenizerService,
    model_name: str,
    progress_callback: Optional[Any] = None,
    hf_token: Optional[str] = None,
) -> tuple[bool, str, Any]:
    """Load tokenizer synchronously. Returns (success, message, tokenizer_or_none)."""
    try:
        tokenizer = tokenizer_service.load_tokenizer(
            model_name,
            local_only=False,
            progress_callback=progress_callback,
            hf_token=hf_token or None,
        )
        return True, tr("install.tokenizer_loaded"), tokenizer
    except TokenizerError as e:
        return False, str(e), None
    except Exception as e:
        return False, str(e), None
