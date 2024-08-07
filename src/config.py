# config.py

import os
import yaml
import logging
from utils.import_helper import add_vendor_to_path

add_vendor_to_path()

logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Construct the path to config.yaml (one level up from the current directory)
        config_path = os.path.join(os.path.dirname(current_dir), 'config.yaml')

        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Configuration file not found. Please ensure config.yaml is present at {config_path}")

        try:
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            logger.info(f"Configuration loaded successfully from {config_path}")
            return config
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            raise

    def get(self, key, default=None):
        """
        Get a configuration value by key.
        """
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                logger.warning(f"Configuration key '{key}' not found. Using default value: {default}")
                return default
        return value

    def validate(self):
        """
        Validate the configuration to ensure all required fields are present.
        """
        required_fields = [
            'tradepost.api_key',
            'interactive_brokers.account',
            'interactive_brokers.host',
            'interactive_brokers.port',
            'interactive_brokers.client_id',
            'interactive_brokers.api_version',
            'trading.cash_buffer',
            'trading.max_position_size'
        ]

        for field in required_fields:
            if self.get(field) is None:
                raise ValueError(f"Missing required configuration field: {field}")

        # Validate specific fields
        max_position_size = self.get('trading.max_position_size')
        if max_position_size is not None:
            try:
                max_position_size = float(max_position_size)
                if not 0 < max_position_size <= 1:
                    raise ValueError("trading.max_position_size must be between 0 and 1")
            except ValueError:
                raise ValueError("trading.max_position_size must be a float between 0 and 1")

        logger.info("Configuration validation successful")


# Create a global instance of the Config class
CONFIG = Config()

# Validate the configuration on import
try:
    CONFIG.validate()
except ValueError as e:
    logger.error(f"Configuration validation failed: {e}")
    raise

# Example usage:
# from config import CONFIG
# api_key = CONFIG.get('tradepost.api_key')
# max_position_size = CONFIG.get('trading.max_position_size', 0.1)  # With default value