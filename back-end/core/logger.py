import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """
    Creates and configures a standardized logger for the application.
    Outputs logs to the console with timestamps and severity levels.
    """
    logger = logging.getLogger(name)
    
    # Prevent adding multiple handlers if the logger already exists
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Log to standard output
        handler = logging.StreamHandler(sys.stdout)
        
        # Standardized formatting: [Time] - [Module] - [Level] - [Message]
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger