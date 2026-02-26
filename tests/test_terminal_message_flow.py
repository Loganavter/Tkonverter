import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from src.core.application.chat_service import ChatService
from src.presenters.workers import ChatLoadWorker

class TerminalMessageFlowTests(unittest.TestCase):
    def setUp(self):
        self.example_file = str(PROJECT_ROOT / "examples" / "result.json")

    def _run_chat_load_worker(self, chat_service: ChatService, file_path: str):
        progress_messages = []
        finished_payloads = []

        worker = ChatLoadWorker(chat_service, file_path)
        worker.signals.progress.connect(progress_messages.append)
        worker.signals.finished.connect(
            lambda success, message, result: finished_payloads.append(
                (success, message, result)
            )
        )
        worker.run()
        return progress_messages, finished_payloads

    def test_single_file_load_terminal_messages_have_correct_order_without_duplicates(self):
        chat_service = ChatService()

        progress_messages, finished_payloads = self._run_chat_load_worker(
            chat_service, self.example_file
        )

        self.assertEqual(len(finished_payloads), 1)
        success, message, chat = finished_payloads[0]
        self.assertTrue(success)
        self.assertEqual(message, "File loaded successfully")
        self.assertIsNotNone(chat)

        expected_order = [
            "Загрузка файла...",
            "Проверка структуры данных чата...",
            "Парсинг сообщений...",
        ]

        cursor = 0
        for expected in expected_order:
            try:
                cursor = progress_messages.index(expected, cursor) + 1
            except ValueError as err:
                raise AssertionError(
                    f"Не найдено ожидаемое сообщение терминала: {expected}. "
                    f"Фактические сообщения: {progress_messages}"
                ) from err

        self.assertEqual(
            len(progress_messages),
            len(set(progress_messages)),
            f"Обнаружены дубликаты сообщений терминала: {progress_messages}",
        )

    def test_repeated_file_load_keeps_same_terminal_call_count(self):
        chat_service = ChatService()

        first_progress, first_finished = self._run_chat_load_worker(
            chat_service, self.example_file
        )
        second_progress, second_finished = self._run_chat_load_worker(
            chat_service, self.example_file
        )

        self.assertEqual(len(first_finished), 1)
        self.assertEqual(len(second_finished), 1)
        self.assertEqual(first_progress, second_progress)
        self.assertEqual(
            len(second_progress),
            len(set(second_progress)),
            "Во втором прогоне появились дубликаты (утечка слушателей).",
        )

if __name__ == "__main__":
    unittest.main()
