import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from config import LOG_DIR, SYSTEM_LOG_FILE, USER_LOG_PREFIX

os.makedirs(LOG_DIR, exist_ok=True)

class LogService:
    def __init__(self):
        self.system_logger = self._create_system_logger()
        self.user_loggers = {}

    def _create_system_logger(self):
        logger = logging.getLogger("system_logger")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = RotatingFileHandler(
                SYSTEM_LOG_FILE,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8"
            )
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)

        return logger

    def get_user_logger(self, user_id: int):
        if user_id in self.user_loggers:
            return self.user_loggers[user_id]

        logger = logging.getLogger(f"user_{user_id}")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            filename = f"{USER_LOG_PREFIX}{user_id}.log"
            handler = RotatingFileHandler(
                filename,
                maxBytes=2 * 1024 * 1024,
                backupCount=2,
                encoding="utf-8"
            )
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - [USER:%(user_id)s] %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        self.user_loggers[user_id] = logger
        return logger

    def log_user_action(self, user_id: int, level: str, message: str):
        logger = self.get_user_logger(user_id)
        extra = {"user_id": user_id}
        if level.lower() == "info":
            logger.info(message, extra=extra)
        elif level.lower() == "warning":
            logger.warning(message, extra=extra)
        elif level.lower() == "error":
            logger.error(message, extra=extra)
        else:
            logger.debug(message, extra=extra)

log_service = LogService()
system_logger = log_service.system_logger