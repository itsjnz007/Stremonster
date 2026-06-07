import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from app.config import CACHE_DIR

class Logger:
    def __init__(self, module_name: str, log_file: str = f"{CACHE_DIR}/logs/app.log", level: int = logging.INFO):
        """
        Initializes a module-specific logger instance.
        """
        self.module_name = module_name.upper()
        
        # 1. Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 2. Structural log formatting (includes your custom method layout)
        log_formatter = logging.Formatter(
            fmt=f"[%(asctime)s] [%(levelname)s] [{self.module_name}] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # 3. Create Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)

        # 4. Create Rotating File Handler (Crucial for server disk safety)
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=2 * 1024 * 1024, # 2MB per file max
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(log_formatter)

        # 5. Build isolated logger instance unique to this module name
        self._internal_logger = logging.getLogger(f"stremonster.{module_name}")
        self._internal_logger.setLevel(level)
        
        # Guard against duplicate handler attachments
        if not self._internal_logger.handlers:
            self._internal_logger.addHandler(console_handler)
            self._internal_logger.addHandler(file_handler)

    def info(self, message: str):
        """Logs an informational message."""
        self._internal_logger.info(f"{message}")

    def error(self, message: str):
        """Logs an error message."""
        self._internal_logger.error(f"{message}")

    def warning(self, message: str):
        """Logs a warning message."""
        self._internal_logger.warning(f"{message}")

    def debug(self, message: str):
        """Logs a debugging message."""
        self._internal_logger.debug(f"{message}")

    def exception(self, message: str):
        """Logs an error along with the complete crash traceback stack."""
        self._internal_logger.exception(f"[exception] {message}")