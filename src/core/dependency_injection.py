

from typing import Any, Callable, Dict, Type, TypeVar

T = TypeVar("T")

class DIContainer:

    def __init__(self):
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable[[], Any]] = {}
        self._transients: Dict[Type, Callable[[], Any]] = {}

    def register_singleton(self, interface: Type[T], factory: Callable[[], T]) -> None:
        self._factories[interface] = factory

    def register_transient(self, interface: Type[T], factory: Callable[[], T]) -> None:
        self._transients[interface] = factory

    def get(self, interface: Type[T]) -> T:

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
        self._singletons.clear()
        self._factories.clear()
        self._transients.clear()

def _register_default_services(container: DIContainer) -> DIContainer:
    from src.core.application.anonymizer_service import AnonymizerService
    from src.core.application.analysis_service import AnalysisService
    from src.core.application.calendar_service import CalendarService
    from src.core.application.chat_memory_service import ChatMemoryService
    from src.core.application.chat_service import ChatService
    from src.core.application.chart_service import ChartService
    from src.core.application.conversion_service import ConversionService
    from src.core.application.export_metrics_service import ExportMetricsService
    from src.core.application.statistics_service import StatisticsService
    from src.core.application.tokenizer_service import TokenizerService
    from src.presenters.preview_service import PreviewService

    container.register_singleton(ChatService, lambda: ChatService())
    container.register_singleton(ChatMemoryService, lambda: ChatMemoryService())
    container.register_singleton(
        ConversionService,
        lambda: ConversionService(
            use_modern_formatters=False,
            chat_memory_service=container.get(ChatMemoryService),
        ),
    )
    container.register_singleton(
        ExportMetricsService,
        lambda: ExportMetricsService(
            chat_memory_service=container.get(ChatMemoryService)
        ),
    )
    container.register_singleton(
        AnalysisService,
        lambda: AnalysisService(
            export_metrics_service=container.get(ExportMetricsService)
        ),
    )
    container.register_singleton(StatisticsService, lambda: StatisticsService())
    container.register_singleton(TokenizerService, lambda: TokenizerService())
    container.register_singleton(AnonymizerService, lambda: AnonymizerService())
    container.register_singleton(ChartService, lambda: ChartService())
    container.register_singleton(CalendarService, lambda: CalendarService())
    container.register_singleton(PreviewService, lambda: PreviewService())
    return container

def setup_container(container: DIContainer | None = None) -> DIContainer:
    if container is None:
        container = DIContainer()
    return _register_default_services(container)

def create_test_container() -> DIContainer:
    return setup_container(container=DIContainer())
