"""
Centralized logging utility for pytol library.

Provides consistent logging across all modules with support for:
- Multiple log levels (DEBUG, INFO, WARNING, ERROR)
- Conditional output based on verbose flag
- Colored output for better readability (optional)
- Consistent formatting with [pytol] prefix
"""

import sys
from enum import Enum
from typing import Optional


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


class PytolLogger:
    """
    Centralized logger for pytol library.
    
    Usage:
        logger = PytolLogger(verbose=True, name="Mission")
        logger.info("Mission created successfully")
        logger.warning("Invalid parameter, using default")
        logger.error("Failed to load map file")
        logger.debug("Internal state: X=123")
    """
    
    def __init__(self, verbose: bool = True, name: Optional[str] = None, min_level: LogLevel = LogLevel.INFO):
        """
        Initialize logger.
        
        Args:
            verbose: If False, suppresses INFO and DEBUG messages
            name: Component name to include in log messages (e.g., "Mission", "ProceduralEngine")
            min_level: Minimum log level to display (defaults to INFO)
        """
        self.verbose = verbose
        self.name = name
        self.min_level = min_level
        
    def _format_message(self, level: LogLevel, message: str) -> str:
        """Format log message with prefix and level."""
        level_prefix = {
            LogLevel.DEBUG: "DEBUG",
            LogLevel.INFO: "",
            LogLevel.WARNING: "Warning",
            LogLevel.ERROR: "ERROR"
        }
        
        prefix_parts = ["[pytol]"]
        if self.name:
            prefix_parts.append(f"[{self.name}]")
        
        level_str = level_prefix[level]
        if level_str:
            prefix_parts.append(f"{level_str}:")
        
        prefix = " ".join(prefix_parts)
        return f"{prefix} {message}" if prefix else message
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if message should be logged based on level and verbose setting."""
        # Always log warnings and errors
        if level in (LogLevel.WARNING, LogLevel.ERROR):
            return True
        
        # Only log info/debug if verbose is True
        if not self.verbose:
            return False
        
        # Check minimum level
        return level.value >= self.min_level.value
    
    def debug(self, message: str):
        """Log debug message (only if verbose=True)."""
        if self._should_log(LogLevel.DEBUG):
            print(self._format_message(LogLevel.DEBUG, message))
    
    def info(self, message: str):
        """Log info message (only if verbose=True)."""
        if self._should_log(LogLevel.INFO):
            print(self._format_message(LogLevel.INFO, message))
    
    def warning(self, message: str):
        """Log warning message (always shown)."""
        if self._should_log(LogLevel.WARNING):
            print(self._format_message(LogLevel.WARNING, message), file=sys.stderr)
    
    def error(self, message: str):
        """Log error message (always shown)."""
        if self._should_log(LogLevel.ERROR):
            print(self._format_message(LogLevel.ERROR, message), file=sys.stderr)
    
    def log(self, message: str, level: LogLevel = LogLevel.INFO):
        """
        Generic log method.
        
        Args:
            message: Message to log
            level: Log level (defaults to INFO)
        """
        if level == LogLevel.DEBUG:
            self.debug(message)
        elif level == LogLevel.INFO:
            self.info(message)
        elif level == LogLevel.WARNING:
            self.warning(message)
        elif level == LogLevel.ERROR:
            self.error(message)


def create_logger(verbose: bool = True, name: Optional[str] = None) -> PytolLogger:
    """
    Factory function to create a logger instance.
    
    Args:
        verbose: If False, suppresses INFO and DEBUG messages
        name: Component name (e.g., "Mission", "ProceduralEngine")
    
    Returns:
        Configured PytolLogger instance
    """
    return PytolLogger(verbose=verbose, name=name)
