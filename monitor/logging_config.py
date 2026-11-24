import logging
from logging.handlers import RotatingFileHandler

from dotenv import dotenv_values


DEFAULT_LEVEL = "DEBUG"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def configure_logging(env_path, log_file, *, console=False):
    settings = dotenv_values(env_path, encoding="utf-8-sig")
    warnings = []

    level = (settings.get("LOG_LEVEL") or DEFAULT_LEVEL).strip().upper()
    if level not in LOG_LEVELS:
        warnings.append(f"LOG_LEVEL inválido. Se usa {DEFAULT_LEVEL}.")
        level = DEFAULT_LEVEL

    limits = {}
    for name, default, minimum in (("LOG_MAX_MB", 5, 0), ("LOG_BACKUP_COUNT", 3, 1)):
        try:
            value = int(settings.get(name) or default)
            if value < minimum:
                raise ValueError
        except ValueError:
            warnings.append(f"{name} debe ser un entero mayor o igual a {minimum}. Se usa {default}.")
            value = default
        limits[name] = value

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=limits["LOG_MAX_MB"] * 1024 * 1024,
        backupCount=limits["LOG_BACKUP_COUNT"],
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger = logging.getLogger("server_monitor")
    logger.setLevel(level)
    logger.propagate = False
    logger.addHandler(file_handler)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    for warning in warnings:
        logger.warning(warning)

    return logger, file_handler
