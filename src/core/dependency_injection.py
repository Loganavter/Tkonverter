"""
Simple DI container for dependency management.

Provides centralized service registration and resolution
for dependency injection pattern implementation.
"""

import logging
from typing import Any, Callable, Dict, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

class DIContainer:
    """Simple container for Dependency Injection."""

    def __init__(self):
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable[[], Any]] = {}
        self._transients: Dict[Type, Callable[[], Any]] = {}

    def register_singleton(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """Registers service as singleton."""
        self._factories[interface] = factory

    def register_transient(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """Registers service as transient (new instance each time)."""
        self._transients[interface] = factory

    def get(self, interface: Type[T]) -> T:
        """Gets service instance."""

        if interface in self._singletons:
            return self._singletons[interface]

        if interface in self._factories:
            instance = self._factories[interface]()
            self._singletons[interface] = instance
            return instance

        if interface in self._transients:
            instance = self._transients[interface]()
            return instance

        raise ValueError(f"Service {interface.__name__} not registered")

    def clear(self) -> None:
        """Clears all registered services."""
        self._singletons.clear()
        self._factories.clear()
        self._transients.clear()

_container = DIContainer()

def get_container() -> DIContainer:
    """Returns global DI container."""
    return _container

def setup_container() -> DIContainer:
    """Sets up DI container with basic services."""
    from core.application.analysis_service import AnalysisService
    from core.application.chat_service import ChatService
    from core.application.conversion_service import ConversionService
    from core.application.tokenizer_service import TokenizerService

    container = get_container()

    container.register_singleton(ChatService, lambda: ChatService())
    container.register_singleton(
        ConversionService, lambda: ConversionService(use_modern_formatters=False)
    )
    container.register_singleton(AnalysisService, lambda: AnalysisService())
    container.register_singleton(TokenizerService, lambda: TokenizerService())

    return container
