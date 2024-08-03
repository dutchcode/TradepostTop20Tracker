import yaml

def load_config(config_path='config.yaml'):
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

CONFIG = load_config()

# You can access config values like this:
# TRADEPOST_API_KEY = CONFIG['tradepost']['api_key']
# IB_ACCOUNT = CONFIG['interactive_brokers']['account']