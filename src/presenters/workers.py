import logging
import subprocess
import sys
import threading
from typing import Any, Dict, Optional, Set

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from core.analysis.tree_analyzer import TreeNode
from core.application.analysis_service import AnalysisService
from core.application.chat_service import ChatLoadError, ChatService
from core.application.conversion_service import ConversionService
from core.application.tokenizer_service import TokenizerError, TokenizerService
from core.domain.models import AnalysisResult, Chat
from resources.translations import tr

logger = logging.getLogger(__name__)

class WorkerSignals(QObject):
    """Signals for worker threads."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, object)

class AIInstallerSignals(QObject):
    """Signals for AI Installer Worker."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

class ChatLoadWorker(QRunnable):
    """Worker for loading chat in a separate thread."""

    def __init__(self, chat_service: ChatService, file_path: str):
        super().__init__()
        self.chat_service = chat_service
        self.file_path = file_path
        self.signals = WorkerSignals()

    def run(self):
        try:
            chat = self.chat_service.load_chat_from_file(self.file_path)
            self.signals.finished.emit(True, tr("File loaded successfully"), chat)
        except ChatLoadError as e:
            self.signals.finished.emit(False, str(e), None)
        except Exception as e:
            logger.error(f"Unexpected error loading chat: {e}")
            self.signals.finished.emit(
                False, tr("Unexpected error: {error}").format(error=str(e)), None
            )

class ConversionWorker(QRunnable):
    """Worker for converting chat to text in a separate thread."""

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
            self.signals.progress.emit(tr("Converting chat..."))
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
    """Worker for analyzing chat in a separate thread."""

    def __init__(
        self,
        analysis_service: AnalysisService,
        chat: Chat,
        config: Dict[str, Any],
        tokenizer: Optional[Any] = None,
    ):
        super().__init__()
        self.analysis_service = analysis_service
        self.chat = chat
        self.config = config
        self.tokenizer = tokenizer
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self._lock = threading.Lock()

    def cancel(self):
        """Запрашивает отмену задачи."""
        with self._lock:
            self._is_cancelled = True

    def is_cancelled(self):
        """Проверяет, была ли запрошена отмена."""
        with self._lock:
            return self._is_cancelled

    def run(self):
        try:

            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            if self.tokenizer:
                result = self.analysis_service.calculate_token_stats(
                    self.chat, self.config, self.tokenizer
                )
            else:
                result = self.analysis_service.calculate_character_stats(
                    self.chat, self.config
                )

            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            self.signals.finished.emit(True, tr("Analysis completed"), result)
        except Exception as e:
            if not self.is_cancelled():
                logger.error(f"Analysis error: {e}")
                self.signals.finished.emit(False, str(e), None)

class TreeBuildWorker(QRunnable):
    """Worker for building analysis tree in a separate thread."""

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
        """Запрашивает отмену задачи."""
        with self._lock:
            self._is_cancelled = True

    def is_cancelled(self):
        """Проверяет, была ли запрошена отмена."""
        with self._lock:
            return self._is_cancelled

    def run(self):
        try:
            self.signals.progress.emit(tr("Building analysis tree..."))

            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            tree = self.analysis_service.build_analysis_tree(
                self.analysis_result, self.config
            )

            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            self.signals.finished.emit(True, tr("Tree built successfully"), tree)
        except Exception as e:
            if not self.is_cancelled():
                logger.error(f"Tree building error: {e}")
                self.signals.finished.emit(False, str(e), None)

class TokenizerLoadWorker(QRunnable):
    """Worker for loading tokenizer in a separate thread."""

    def __init__(self, tokenizer_service: TokenizerService, model_name: str):
        super().__init__()
        self.tokenizer_service = tokenizer_service
        self.model_name = model_name
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self._lock = threading.Lock()

    def cancel(self):
        """Запрашивает отмену задачи."""
        with self._lock:
            self._is_cancelled = True

    def is_cancelled(self):
        """Проверяет, была ли запрошена отмена."""
        with self._lock:
            return self._is_cancelled

    def run(self):
        try:

            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            progress_callback = lambda msg: self.signals.progress.emit(msg)
            tokenizer = self.tokenizer_service.load_tokenizer(
                self.model_name, local_only=False, progress_callback=progress_callback
            )

            if self.is_cancelled():
                self.signals.finished.emit(False, "Cancelled", None)
                return

            self.signals.finished.emit(
                True, tr("Tokenizer loaded successfully"), tokenizer
            )
        except TokenizerError as e:
            if not self.is_cancelled():
                self.signals.finished.emit(False, str(e), None)
        except Exception as e:
            if not self.is_cancelled():
                logger.error(f"Unexpected tokenizer error: {e}")
                self.signals.finished.emit(False, str(e), None)

class AIInstallerWorker(QRunnable):
    """Worker for installing/removing AI components."""

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
        """Removes model from HuggingFace cache."""
        if not self.model_name:
            self.signals.finished.emit(False, tr("Model name not provided."))
            return

        try:
            from huggingface_hub import scan_cache_dir
        except ImportError:
            self.signals.finished.emit(False, tr("huggingface_hub is not installed."))
            return

        try:
            self.signals.progress.emit(tr("Scanning cache for model..."))
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
                self.signals.progress.emit(tr("Model not found in cache."))
                self.signals.finished.emit(
                    True, tr("Model cache removed successfully.")
                )
                return

            self.signals.progress.emit(tr("Found model, preparing to delete..."))
            revisions_to_delete = {rev.commit_hash for rev in repo_info.revisions}

            delete_strategy = hf_cache_info.delete_revisions(*revisions_to_delete)
            self.signals.progress.emit(
                tr("Will free: {size}").format(
                    size=delete_strategy.expected_freed_size_str
                )
            )
            self.signals.progress.emit(tr("Deleting model from cache..."))
            delete_strategy.execute()

            self.signals.finished.emit(True, tr("Model cache removed successfully."))
        except Exception as e:
            self.signals.finished.emit(False, str(e))

    def _install_dependencies(self):
        """Installs transformers dependencies."""
        packages = ["transformers[sentencepiece,torch]", "huggingface_hub"]
        if sys.prefix == sys.base_prefix:
            error_msg = tr(
                "Refusing to install packages into the system Python. Please run this application from a virtual environment (venv)."
            )
            self.signals.progress.emit(f"ERROR: {error_msg}")
            self.signals.finished.emit(False, error_msg)
            return
        command = [sys.executable, "-m", "pip", "install", "--upgrade", *packages]
        try:
            self.signals.progress.emit(
                tr("Executing: {command}").format(command=" ".join(command))
            )
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            for line in iter(process.stdout.readline, ""):
                self.signals.progress.emit(line.strip())

            process.wait()

            if process.returncode == 0:
                self.signals.finished.emit(True, tr("Operation successful."))
            else:
                self.signals.finished.emit(
                    False,
                    tr("Operation failed with code: {code}").format(
                        code=process.returncode
                    ),
                )
        except Exception as e:
            self.signals.finished.emit(False, str(e))
