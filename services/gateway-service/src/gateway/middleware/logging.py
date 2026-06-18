import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """Configura structlog con salida JSON estructurada para CloudWatch."""
    log_level_num = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level_num,
    )

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors + [structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(log_level_num),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
