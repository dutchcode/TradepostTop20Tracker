import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradepostAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://tradepost.ai/api/v1"
        logger.info(f"TradepostAPI initialized with base URL: {self.base_url}")

    def get_top20(self, date=None):
        endpoint = f"{self.base_url}/top20"
        params = {"api_key": self.api_key}
        if date:
            params["date"] = date

        logger.info(f"Making GET request to {endpoint}")
        logger.debug(f"Request parameters: {params}")

        try:
            response = requests.get(endpoint, params=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses

            logger.info(f"Successful API call to {endpoint}")
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response headers: {response.headers}")

            data = response.json()
            logger.debug(f"Response data: {data}")

            return data

        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err}")
            logger.error(f"Response content: {response.text}")
            raise

        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f"Error connecting to the API: {conn_err}")
            raise

        except requests.exceptions.Timeout as timeout_err:
            logger.error(f"Timeout error: {timeout_err}")
            raise

        except requests.exceptions.RequestException as req_err:
            logger.error(f"An error occurred while making the request: {req_err}")
            raise

        except ValueError as json_err:
            logger.error(f"Error decoding JSON response: {json_err}")
            logger.error(f"Response content: {response.text}")
            raise

    # Add more methods as needed for other API endpoints

    def __str__(self):
        return f"TradepostAPI(base_url={self.base_url})"

    def __repr__(self):
        return self.__str__()