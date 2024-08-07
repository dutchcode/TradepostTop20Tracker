# tradepost_api.py

import requests
import logging
from datetime import datetime, timedelta
from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout

logger = logging.getLogger(__name__)


class TradepostAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://tradepost.ai/api/v1"
        logger.info(f"TradepostAPI initialized with base URL: {self.base_url}")

    def _make_request(self, endpoint, params=None):
        """
        Make a GET request to the Tradepost API.
        """
        url = f"{self.base_url}/{endpoint}"
        params = params or {}
        params['api_key'] = self.api_key

        logger.info(f"Making GET request to {url}")
        logger.debug(f"Request parameters: {params}")

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            logger.info(f"Successful API call to {url}")
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response headers: {response.headers}")
            return response.json()
        except HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err}")
            logger.error(f"Response content: {response.text}")
            raise
        except ConnectionError as conn_err:
            logger.error(f"Error connecting to the API: {conn_err}")
            raise
        except Timeout as timeout_err:
            logger.error(f"Timeout error: {timeout_err}")
            raise
        except RequestException as req_err:
            logger.error(f"An error occurred while making the request: {req_err}")
            raise
        except ValueError as json_err:
            logger.error(f"Error decoding JSON response: {json_err}")
            logger.error(f"Response content: {response.text}")
            raise

    def get_top20(self, date=None):
        """
        Get the Top 20 stocks from Tradepost.

        :param date: Optional date string in format 'YYYY-MM-DD'. If not provided, uses current date.
        :return: Dictionary containing Top 20 data.
        """
        endpoint = "top20"
        params = {}

        if date:
            try:
                datetime.strptime(date, '%Y-%m-%d')
                params['date'] = date
            except ValueError:
                logger.error(f"Invalid date format: {date}. Expected format: YYYY-MM-DD")
                raise ValueError("Invalid date format. Expected format: YYYY-MM-DD")

        try:
            data = self._make_request(endpoint, params)
            logger.info(f"Successfully retrieved Top 20 data for date: {data.get('date', 'Unknown')}")
            logger.debug(f"Top 20 data: {data}")
            return data
        except Exception as e:
            logger.error(f"Failed to retrieve Top 20 data: {e}")
            raise

    def get_historical_top20(self, start_date, end_date):
        """
        Get historical Top 20 data for a date range.

        :param start_date: Start date string in format 'YYYY-MM-DD'
        :param end_date: End date string in format 'YYYY-MM-DD'
        :return: List of dictionaries containing historical Top 20 data.
        """
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            logger.error(f"Invalid date format. start_date: {start_date}, end_date: {end_date}")
            raise ValueError("Invalid date format. Expected format: YYYY-MM-DD")

        if start > end:
            logger.error(f"Start date {start_date} is after end date {end_date}")
            raise ValueError("Start date must be before or equal to end date")

        historical_data = []
        current_date = start
        while current_date <= end:
            date_str = current_date.strftime('%Y-%m-%d')
            try:
                data = self.get_top20(date_str)
                historical_data.append(data)
                logger.info(f"Retrieved Top 20 data for {date_str}")
            except Exception as e:
                logger.warning(f"Failed to retrieve Top 20 data for {date_str}: {e}")
            current_date += timedelta(days=1)

        logger.info(f"Retrieved historical Top 20 data from {start_date} to {end_date}")
        return historical_data

    def __str__(self):
        return f"TradepostAPI(base_url={self.base_url})"

    def __repr__(self):
        return self.__str__()