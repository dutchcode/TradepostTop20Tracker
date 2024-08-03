import requests

class TradepostAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://tradepost.ai/api/v1"

    def get_top20(self, date=None):
        endpoint = f"{self.base_url}/top20"
        params = {"api_key": self.api_key}
        if date:
            params["date"] = date

        response = requests.get(endpoint, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses

        return response.json()

    # Add more methods as needed for other API endpoints