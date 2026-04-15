import logging
import logging.handlers
import sys
import structlog
from pathlib import Path
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    logs_dir: str = "data/logs"
) -> None:

    if log_to_file:
        Path(logs_dir).mkdir(parents=True, exist_ok=True)

    handlers = []

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    handlers.append(console_handler)

    if log_to_file:
        log_filename = f"data/logs/rag_system_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            filename = log_filename,
            maxBytes = 10 * 1024 * 1024,
            backupCount = 5,
            encoding = "utf-8"
        )
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    logging.basicConfig(
        level = log_level,
        handlers = handlers,
        format = "%(message)s"
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.ERROR) # Silences the telemetry "failed to send" errors
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING) # Silence standard access logs (keep errors)

    structlog.configure(
        processors = [
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt = "iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.stdlib.PositionalArgumentsFormatter(),

            structlog.dev.ConsoleRenderer()
            if log_level == "DEBUG"
            else structlog.processors.JSONRenderer()
        ],

        wrapper_class = structlog.stdlib.BoundLogger,
        context_class = dict,
        logger_factory = structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use = True
    )

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
