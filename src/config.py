import yaml
import os


def load_config():
    config_path = 'config.yaml'
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuration file not found. Please copy config.example.yaml to {config_path} and fill in your values.")

    with open(config_path, 'r') as file:
        return yaml.safe_load(file)


CONFIG = load_config()