try:
    from core.logging import setup_logging, setup_simple_logging, get_log_directory
    _logging_available = True
except ImportError:
    _logging_available = False
    setup_logging = None
    setup_simple_logging = None
    get_log_directory = None

__all__ = ['setup_logging', 'setup_simple_logging', 'get_log_directory']

