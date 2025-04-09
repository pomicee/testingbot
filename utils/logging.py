import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name, level=logging.INFO):
    """Set up a logger with file and console handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if logger.hasHandlers():
        return logger
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )  
    os.makedirs('logs', exist_ok=True)
    file_handler = RotatingFileHandler(
        f'logs/{name.split(".")[-1]}.log',
        maxBytes=5*1024*1024, 
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger
