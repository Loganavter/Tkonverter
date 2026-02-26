import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from src.core.dependency_injection import (
    DIContainer,
    create_test_container,
    setup_container,
)

class _SampleService:
    pass

class DIContainerTests(unittest.TestCase):
    def test_singleton_registration_returns_same_instance(self):
        container = DIContainer()
        container.register_singleton(_SampleService, lambda: _SampleService())

        first = container.get(_SampleService)
        second = container.get(_SampleService)

        self.assertIs(first, second)

    def test_transient_registration_returns_new_instance(self):
        container = DIContainer()
        container.register_transient(_SampleService, lambda: _SampleService())

        first = container.get(_SampleService)
        second = container.get(_SampleService)

        self.assertIsNot(first, second)

    def test_setup_container_creates_isolated_instances_by_default(self):
        first_container = setup_container()
        second_container = setup_container()

        self.assertIsNot(first_container, second_container)

    def test_create_test_container_is_isolated_from_runtime_containers(self):
        test_container = create_test_container()
        runtime_container = setup_container()

        self.assertIsNot(test_container, runtime_container)

if __name__ == "__main__":
    unittest.main()
