import os
import yaml


def load_config():
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the path to config.yaml (one level up from the current directory)
    config_path = os.path.join(os.path.dirname(current_dir), 'config.yaml')

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuration file not found. Please copy config.example.yaml to {config_path} and fill in your values.")

    with open(config_path, 'r') as file:
        return yaml.safe_load(file)


CONFIG = load_config()