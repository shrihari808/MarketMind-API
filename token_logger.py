# token_logger.py
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import pytz
import json

def setup_logger():
    """Sets up a logger to save token usage information to a file with daily rotation."""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger('token_usage')
    logger.setLevel(logging.INFO)

    # Use TimedRotatingFileHandler for daily log rotation
    handler = TimedRotatingFileHandler(
        os.path.join(log_dir, 'token_usage.log'),
        when="midnight",
        interval=1,
        backupCount=30  # Keep 30 days of logs
    )

    # Formatter to output log messages in a structured way
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)

    # Avoid adding handlers multiple times
    if not logger.handlers:
        logger.addHandler(handler)

    return logger

LOGGER = setup_logger()

def log_token_usage(model_name: str, input_tokens: int, output_tokens: int, total_tokens: int, purpose: str):
    """
    Logs the token usage of an LLM call to a file.

    Args:
        model_name (str): The name of the LLM model used.
        input_tokens (int): The number of tokens in the input/prompt.
        output_tokens (int): The number of tokens in the output/completion.
        total_tokens (int): The total number of tokens used.
        purpose (str): A description of the LLM call's purpose.
    """
    ist = pytz.timezone('Asia/Kolkata')
    timestamp_ist = datetime.now(ist).isoformat()

    log_entry = {
        "timestamp_ist": timestamp_ist,
        "model_name": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "purpose": purpose,
    }

    LOGGER.info(json.dumps(log_entry))