# main.py

import time
import logging
from utils.import_helper import add_vendor_to_path

add_vendor_to_path()
from decimal import Decimal
from datetime import datetime, timedelta
import pytz
from config import CONFIG
from tradepost_api import TradepostAPI
from ib_connection import IBConnection
from portfolio_manager import PortfolioManager
from trade_executor import TradeExecutor

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_top20_data(data):
    logger.debug(f"Raw Top20 data: {data}")
    processed_data = {}
    for constituent in data['constituents']:
        ticker = constituent.get('ticker')
        isin = constituent.get('isin')
        exchange = constituent.get('exchange')

        if not ticker or not isin or not exchange:
            logger.warning(f"Missing essential data for constituent: {constituent}")
            continue

        processed_data[ticker] = {
            'isin': isin,
            'exchange': exchange,
            'name': constituent.get('name'),
            'rank': constituent.get('rank')
        }

    logger.debug(f"Processed Top20 data: {processed_data}")
    return processed_data

def get_current_prices(ib, processed_top20):
    prices = {}
    for ticker, data in processed_top20.items():
        retries = 3
        while retries > 0:
            try:
                if ib.is_market_open(data['exchange']):
                    price = ib.get_market_price(data['isin'], ticker, data['exchange'], data['name'])
                    if price is not None:
                        prices[ticker] = price
                        logger.info(f"Got price for {ticker} ({data['name']}): {price}")
                        break
                    else:
                        logger.warning(f"Failed to get price for {ticker} ({data['name']}). Retries left: {retries - 1}")
                        retries -= 1
                else:
                    logger.info(f"Market for {ticker} ({data['exchange']}) is closed. Skipping.")
                    break
            except Exception as e:
                logger.error(f"Failed to get price for {ticker} ({data['name']}): {e}")
                retries -= 1
            time.sleep(1)  # Add a small delay between retries

        if ticker not in prices:
            logger.error(f"Unable to get price for {ticker} ({data['name']}) after all retries or market closed. Skipping this stock.")

    return prices

def main():
    logger.info("Starting the TradepostTop20Tracker")

    if 'tradepost' not in CONFIG or 'api_key' not in CONFIG['tradepost']:
        logger.error("Tradepost API key not found in configuration")
        return

    tradepost = TradepostAPI(CONFIG['tradepost']['api_key'])
    logger.info(f"TradepostAPI initialized: {tradepost}")

    if 'interactive_brokers' not in CONFIG:
        logger.error("Interactive Brokers configuration not found")
        return

    ib_config = CONFIG['interactive_brokers']
    ib = IBConnection(ib_config['host'], ib_config['port'], ib_config['client_id'], ib_config['api_version'])
    pm = PortfolioManager(ib)
    te = TradeExecutor(ib)

    try:
        logger.info("Testing TradepostAPI connection...")
        try:
            top20_data = tradepost.get_top20()
            logger.info("Successfully fetched Top20 data")
            logger.debug(f"Top20 data: {top20_data}")
        except Exception as e:
            logger.error(f"Failed to fetch Top20 data: {e}")
            return

        logger.info("Attempting to connect to Interactive Brokers")
        try:
            ib.connect()
        except TimeoutError as e:
            logger.error(f"Failed to connect to Interactive Brokers: {e}")
            return
        except Exception as e:
            logger.error(f"Failed to connect to Interactive Brokers: {e}")
            return

        while True:
            try:
                if not ib.is_connected():
                    logger.error("Lost connection to Interactive Brokers. Attempting to reconnect...")
                    ib.connect()

                top20_data = tradepost.get_top20()
                logger.info(f"Fetched Top20 data for date: {top20_data['date']}")

                processed_top20 = process_top20_data(top20_data)
                logger.debug(f"Processed Top20 data: {processed_top20}")

                current_prices = get_current_prices(ib, processed_top20)
                logger.debug(f"Current prices: {current_prices}")

                valid_top20 = {ticker: data for ticker, data in processed_top20.items() if ticker in current_prices}
                for ticker, data in valid_top20.items():
                    data['price'] = current_prices[ticker]

                logger.debug(f"Valid Top20 data with prices: {valid_top20}")

                current_portfolio = pm.get_current_portfolio()
                logger.info(f"Current portfolio: {current_portfolio}")

                sell_orders, buy_orders = pm.calculate_rebalance_orders(current_portfolio, valid_top20)

                if sell_orders:
                    logger.info(f"Executing sell orders: {sell_orders}")
                    for order in sell_orders:
                        te.execute_order(order)

                if buy_orders:
                    logger.info(f"Executing buy orders: {buy_orders}")
                    for order in buy_orders:
                        te.execute_order(order)

                # Wait for a shorter period before the next iteration
                time.sleep(300)  # Wait for 5 minutes before the next check

            except Exception as e:
                logger.error(f"An error occurred: {e}")
                time.sleep(300)  # Wait for 5 minutes before retrying

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        logger.critical(f"Critical error occurred: {e}")
    finally:
        logger.info("Disconnecting from Interactive Brokers")
        ib.disconnect()

if __name__ == "__main__":
    main()