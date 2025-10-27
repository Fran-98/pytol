"""
Centralized logging configuration for pytol library.

Replaces scattered print() statements with proper logging framework.
"""

import logging
import sys
from pathlib import Path

# Default log level
DEFAULT_LOG_LEVEL = logging.INFO

# Logger name for the library
PYTOL_LOGGER_NAME = "pytol"


def setup_logger(
    name: str = PYTOL_LOGGER_NAME,
    level: int = DEFAULT_LOG_LEVEL,
    log_file: str = None,
    console: bool = True
) -> logging.Logger:
    """
    Configure and return a logger for pytol.
    
    Args:
        name: Logger name (default: 'pytol')
        level: Logging level (default: INFO)
        log_file: Optional file path for log output
        console: Whether to output to console (default: True)
        
    Returns:
        Configured logger instance
        
    Examples:
        >>> # Basic usage
        >>> logger = setup_logger()
        >>> logger.info("Mission generated successfully")
        
        >>> # With file output
        >>> logger = setup_logger(log_file="mission_gen.log")
        
        >>> # Debug mode
        >>> logger = setup_logger(level=logging.DEBUG)
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Get an existing logger or create a default one.
    
    Args:
        name: Logger name (default: 'pytol')
        
    Returns:
        Logger instance
        
    Examples:
        >>> logger = get_logger("pytol.terrain")
        >>> logger.debug("Checking terrain height...")
    """
    logger_name = f"{PYTOL_LOGGER_NAME}.{name}" if name else PYTOL_LOGGER_NAME
    logger = logging.getLogger(logger_name)
    
    # If logger has no handlers, set up a default configuration
    if not logger.handlers:
        logger.setLevel(DEFAULT_LOG_LEVEL)
        # Use parent logger's handlers if available
        if not logger.parent or not logger.parent.handlers:
            setup_logger(PYTOL_LOGGER_NAME)
    
    return logger


# Module-level logger for convenience
logger = get_logger()
