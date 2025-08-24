"""
Service for managing tokenizers.

Responsible for loading, caching and managing tokenizers
from Hugging Face without direct dependency on PyQt.
"""

import importlib.util
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

TRANSFORMERS_AVAILABLE = importlib.util.find_spec("transformers") is not None

class TokenizerError(Exception):
    """Exception when working with tokenizer."""

    pass

class TokenizerService:
    """Service for managing tokenizers."""

    def __init__(self):
        self._current_tokenizer: Optional[Any] = None
        self._current_model_name: Optional[str] = None
        self._default_model = "google/gemma-2b"

    def is_transformers_available(self) -> bool:
        """Checks if transformers libraries are available."""
        return TRANSFORMERS_AVAILABLE

    def load_tokenizer(
        self,
        model_name: str,
        local_only: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Any:
        """
        Loads tokenizer.

        Args:
            model_name: Model name to load
            local_only: Use only local files
            progress_callback: Function for progress reporting

        Returns:
            Any: Loaded tokenizer

        Raises:
            TokenizerError: On loading error
        """
        if not TRANSFORMERS_AVAILABLE:
            raise TokenizerError("Transformers library is not installed")

        try:
            if progress_callback:
                progress_callback(f"Loading tokenizer {model_name}...")

            from transformers import AutoTokenizer

            if local_only:

                tokenizer = AutoTokenizer.from_pretrained(
                    model_name, local_files_only=True
                )
            else:

                tokenizer = AutoTokenizer.from_pretrained(model_name)

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
        except Exception as e:
            raise TokenizerError(f"Unexpected error: {e}")

    def load_default_tokenizer(
        self, progress_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[Any]:
        """
        Loads default tokenizer STRICTLY from local cache.
        Does NOT attempt to download model from internet.

        Args:
            progress_callback: Function for progress reporting

        Returns:
            Optional[Any]: Tokenizer or None if failed to load
        """
        if not TRANSFORMERS_AVAILABLE:
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
        """Returns the currently loaded tokenizer."""
        return self._current_tokenizer

    def get_current_model_name(self) -> Optional[str]:
        """Returns the name of the current model."""
        return self._current_model_name

    def has_tokenizer_loaded(self) -> bool:
        """Checks if tokenizer is loaded."""
        return self._current_tokenizer is not None

    def is_tokenizer_loaded(self) -> bool:
        """Alias for has_tokenizer_loaded method."""
        return self.has_tokenizer_loaded()

    def unload_tokenizer(self):
        """Unloads the current tokenizer."""
        self._current_tokenizer = None
        self._current_model_name = None

    def get_tokenizer_info(self) -> Dict[str, Any]:
        """
        Returns information about the current tokenizer.

        Returns:
            Dict[str, Any]: Information about the tokenizer
        """
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
            logger.warning(f"Error getting tokenizer info: {e}")
            return {
                "loaded": True,
                "model_name": self._current_model_name,
                "vocab_size": None,
                "model_max_length": None,
                "error": str(e),
            }

    def tokenize_text(self, text: str) -> int:
        """
        Tokenizes text and returns the number of tokens.

        Args:
            text: Text to tokenize

        Returns:
            int: Number of tokens

        Raises:
            TokenizerError: If tokenizer is not loaded
        """
        if not self._current_tokenizer:
            raise TokenizerError("Tokenizer not loaded")

        try:
            tokens = self._current_tokenizer.encode(text)
            return len(tokens)
        except Exception as e:
            raise TokenizerError(f"Tokenization error: {e}")

    def get_available_models(self) -> list[str]:
        """
        Returns a list of available models.

        Returns:
            list[str]: List of model names
        """

        return [
            "google/gemma-2b",
            "microsoft/DialoGPT-medium",
            "openai-gpt",
            "gpt2",
            "facebook/opt-125m",
            "EleutherAI/gpt-neo-125M",
        ]

    def get_default_model_name(self) -> str:
        """Returns the default model name."""
        return self._default_model

    def set_default_model(self, model_name: str):
        """
        Sets the default model.

        Args:
            model_name: Model name
        """
        self._default_model = model_name

    def check_model_cache(self, model_name: str) -> Dict[str, Any]:
        """
        Checks if a model exists in the local cache.

        Args:
            model_name: Model name to check

        Returns:
            Dict[str, Any]: Information about model availability in cache
        """
        if not TRANSFORMERS_AVAILABLE:
            return {"available": False, "reason": "transformers not installed"}

        try:

            from huggingface_hub import scan_cache_dir

            try:
                hf_cache_info = scan_cache_dir()

                repo_info = next(
                    (
                        repo
                        for repo in hf_cache_info.repos
                        if repo.repo_id == model_name
                    ),
                    None,
                )

                if repo_info:
                    return {
                        "available": True,
                        "model_name": model_name,
                        "cache_size": len(repo_info.revisions),
                    }
                else:
                    return {"available": False, "reason": "not in cache"}

            except Exception:

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
        """
        Gets information for clearing model cache.

        Args:
            model_name: Model name

        Returns:
            Dict[str, Any]: Information for clearing cache
        """
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
