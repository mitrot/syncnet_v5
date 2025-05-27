"""Logging configuration for syncnet_v5"""

import logging
import logging.handlers
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class LogConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    log_file: Optional[str] = None
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    console: bool = True

def setup_logger(
    name: str,
    config: Optional[LogConfig] = None,
    extra_handlers: Optional[list[logging.Handler]] = None
) -> logging.Logger:
    """Setup logger with configuration
    
    Args:
        name: Logger name
        config: Logging configuration
        extra_handlers: Additional logging handlers
        
    Returns:
        Configured logger
    """
    if config is None:
        config = LogConfig()
        
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.level.upper()))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt=config.format,
        datefmt=config.date_format
    )
    
    # Add console handler if enabled
    if config.console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Add file handler if log file specified
    if config.log_file:
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(config.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.handlers.RotatingFileHandler(
            filename=config.log_file,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Add extra handlers
    if extra_handlers:
        for handler in extra_handlers:
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """Get logger with default configuration
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return setup_logger(name)

# Default loggers
server_logger = get_logger("syncnet.server")
client_logger = get_logger("syncnet.client")
network_logger = get_logger("syncnet.network")
security_logger = get_logger("syncnet.security")
consensus_logger = get_logger("syncnet.consensus")

# Log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

# Log formats
LOG_FORMATS = {
    "default": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "simple": "%(levelname)s - %(message)s",
    "detailed": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    "json": '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
}

# Date formats
DATE_FORMATS = {
    "default": "%Y-%m-%d %H:%M:%S",
    "iso": "%Y-%m-%dT%H:%M:%S.%fZ",
    "simple": "%H:%M:%S"
}

def create_log_config(
    level: str = "INFO",
    format: str = "default",
    date_format: str = "default",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console: bool = True
) -> LogConfig:
    """Create logging configuration
    
    Args:
        level: Log level
        format: Log format name
        date_format: Date format name
        log_file: Log file path
        max_bytes: Maximum log file size
        backup_count: Number of backup files
        console: Whether to log to console
        
    Returns:
        Logging configuration
    """
    return LogConfig(
        level=level,
        format=LOG_FORMATS.get(format, LOG_FORMATS["default"]),
        date_format=DATE_FORMATS.get(date_format, DATE_FORMATS["default"]),
        log_file=log_file,
        max_bytes=max_bytes,
        backup_count=backup_count,
        console=console
    )

def update_log_level(logger: logging.Logger, level: str):
    """Update logger level
    
    Args:
        logger: Logger to update
        level: New log level
    """
    if level.upper() in LOG_LEVELS:
        logger.setLevel(LOG_LEVELS[level.upper()])
        for handler in logger.handlers:
            handler.setLevel(LOG_LEVELS[level.upper()])

def update_log_format(logger: logging.Logger, format: str):
    """Update logger format
    
    Args:
        logger: Logger to update
        format: New log format name
    """
    if format in LOG_FORMATS:
        formatter = logging.Formatter(
            fmt=LOG_FORMATS[format],
            datefmt=DATE_FORMATS["default"]
        )
        for handler in logger.handlers:
            handler.setFormatter(formatter)

def add_file_handler(
    logger: logging.Logger,
    log_file: str,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5
):
    """Add file handler to logger
    
    Args:
        logger: Logger to update
        log_file: Log file path
        max_bytes: Maximum log file size
        backup_count: Number of backup files
    """
    # Create directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setFormatter(logger.handlers[0].formatter)
    logger.addHandler(file_handler)

def remove_file_handler(logger: logging.Logger, log_file: str):
    """Remove file handler from logger
    
    Args:
        logger: Logger to update
        log_file: Log file path to remove
    """
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            if handler.baseFilename == os.path.abspath(log_file):
                logger.removeHandler(handler)
                handler.close()
                break 