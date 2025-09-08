

from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool

class CancellableTaskManager(QObject):
    """
    Управляет запуском и отменой одного типа фоновых задач,
    гарантируя, что выполняется только самая последняя.
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, object)

    def __init__(self, worker_class, parent=None):
        super().__init__(parent)
        self._worker_class = worker_class
        self._current_worker = None
        self._pending_args = None
        self._threadpool = QThreadPool.globalInstance()

    def submit(self, *args, **kwargs):
        """
        Запускает новую задачу, отменяя любую предыдущую.
        """

        if self._current_worker:
            self._current_worker.cancel()

        self._pending_args = (args, kwargs)

        if not self._current_worker:
            self._start_pending_task()

    def _start_pending_task(self):
        """Запускает ожидающую задачу, если она есть."""
        if self._pending_args is None:
            return

        args, kwargs = self._pending_args
        self._pending_args = None

        self._current_worker = self._worker_class(*args, **kwargs)
        self._current_worker.signals.progress.connect(self.progress)
        self._current_worker.signals.finished.connect(self._on_worker_finished)
        self._threadpool.start(self._current_worker)

    def _on_worker_finished(self, success, message, result):
        """Слот, вызываемый по завершении воркера."""

        if message != "Cancelled":
            self.finished.emit(success, message, result)

        self._current_worker = None

        if self._pending_args:
            self._start_pending_task()
