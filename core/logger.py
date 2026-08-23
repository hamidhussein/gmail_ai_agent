"""
GmailAI Assistant - Logging System
"""
import os
import sys
import logging
import platform
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(log_dir: Path = None, level: int = logging.INFO) -> logging.Logger:
    """Configures root application logger with rotating file and console handlers."""
    if log_dir is None:
        log_dir = Path.home() / ".gmailai" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "gmailai.log"
    audit_file = log_dir / "audit.log"

    # Main logger
    logger = logging.getLogger("GmailAI")
    logger.setLevel(level)

    # Avoid duplicate handlers if setup is called multiple times
    if logger.handlers:
        return logger

    # Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s] [%(name)s:%(threadName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Main rotating file handler (5 MB max, up to 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Audit logger for compliance & security records
    audit_logger = logging.getLogger("GmailAI.Audit")
    audit_logger.setLevel(logging.INFO)
    audit_handler = RotatingFileHandler(
        audit_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8"
    )
    audit_formatter = logging.Formatter(
        "[%(asctime)s] [AUDIT] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    audit_handler.setFormatter(audit_formatter)
    audit_logger.addHandler(audit_handler)

    _log_startup_banner(logger, log_dir)
    return logger


def _log_startup_banner(logger: logging.Logger, log_dir: Path) -> None:
    """Logs a startup banner with key system and config information."""
    try:
        from app.config import config_manager
        db_path = config_manager.db_path
        cfg_path = config_manager.config_file
        version = config_manager.config.version
        ai_mode = config_manager.config.ai_mode
    except Exception:
        db_path = cfg_path = version = ai_mode = "unavailable"

    banner_lines = [
        "=" * 70,
        f"  GmailAI Assistant  v{version}  —  Starting Up",
        "=" * 70,
        f"  Python     : {sys.version.split()[0]}",
        f"  Platform   : {platform.system()} {platform.release()} ({platform.machine()})",
        f"  AI Mode    : {ai_mode}",
        f"  Database   : {db_path}",
        f"  Config     : {cfg_path}",
        f"  Log Dir    : {log_dir}",
        "=" * 70,
    ]
    for line in banner_lines:
        logger.info(line)


def get_logger(name: str = "GmailAI") -> logging.Logger:
    """Get a named child logger."""
    return logging.getLogger(f"GmailAI.{name}")
