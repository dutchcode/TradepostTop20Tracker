# main.py

import time
import logging
from decimal import Decimal
from datetime import datetime, timedelta
import pytz
from utils.import_helper import add_vendor_to_path

add_vendor_to_path()

from config import CONFIG
from tradepost_api import TradepostAPI
from broker import IBBroker
from portfolio_manager import PortfolioManager

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


def get_current_prices(broker, processed_top20):
    prices = {}
    for ticker, data in processed_top20.items():
        retries = 3
        while retries > 0:
            try:
                if broker.is_market_open(data['exchange']):
                    price = broker.get_market_price(data['isin'], ticker, data['exchange'], data['name'])
                    if price is not None:
                        prices[ticker] = price
                        logger.info(f"Got price for {ticker} ({data['name']}): {price}")
                        break
                    else:
                        logger.warning(
                            f"Failed to get price for {ticker} ({data['name']}). Retries left: {retries - 1}")
                        retries -= 1
                else:
                    logger.info(f"Market for {ticker} ({data['exchange']}) is closed. Will retry later.")
                    break
            except Exception as e:
                logger.error(f"Failed to get price for {ticker} ({data['name']}): {e}")
                retries -= 1
            time.sleep(60)  # Wait for 1 minute before retrying

        if ticker not in prices:
            logger.error(f"Unable to get price for {ticker} ({data['name']}) after all retries. Skipping this stock.")

    return prices


def wait_for_market_open(broker, exchange):
    while not broker.is_market_open(exchange):
        next_check = broker.get_next_market_open(exchange)
        wait_time = (next_check - datetime.now(pytz.utc)).total_seconds()
        logger.info(f"Market for {exchange} is closed. Next check in {wait_time / 60:.2f} minutes.")
        time.sleep(min(wait_time, 3600))  # Wait for the calculated time or max 1 hour


def main():
    logger.info("Starting the TradepostTop20Tracker")

    tradepost_api_key = CONFIG.get('tradepost.api_key')
    if not tradepost_api_key:
        logger.error("Tradepost API key not found in configuration")
        return

    tradepost = TradepostAPI(tradepost_api_key)
    logger.info(f"TradepostAPI initialized: {tradepost}")

    ib_config = CONFIG.get('interactive_brokers')
    if not ib_config:
        logger.error("Interactive Brokers configuration not found")
        return

    broker = IBBroker(ib_config['host'], ib_config['port'], ib_config['client_id'], ib_config['api_version'])
    pm = PortfolioManager(broker)

    try:
        logger.info("Attempting to connect to Interactive Brokers")
        broker.connect()

        while True:
            try:
                if not broker.is_connected():
                    logger.error("Lost connection to Interactive Brokers. Attempting to reconnect...")
                    broker.connect()

                logger.info("Fetching Top20 data from Tradepost")
                top20_data = tradepost.get_top20()
                logger.info(f"Fetched Top20 data for date: {top20_data['date']}")

                processed_top20 = process_top20_data(top20_data)
                logger.debug(f"Processed Top20 data: {processed_top20}")

                if not processed_top20:
                    logger.warning("No valid stocks in Top20 data. Waiting before retry.")
                    time.sleep(300)  # Wait for 5 minutes before retrying
                    continue

                current_prices = get_current_prices(broker, processed_top20)
                if not current_prices:
                    logger.warning("No valid prices available. Waiting before retry.")
                    time.sleep(300)  # Wait for 5 minutes
                    continue
                logger.debug(f"Current prices: {current_prices}")

                valid_top20 = {ticker: data for ticker, data in processed_top20.items() if ticker in current_prices}
                for ticker, data in valid_top20.items():
                    data['price'] = current_prices[ticker]

                logger.debug(f"Valid Top20 data with prices: {valid_top20}")

                if not valid_top20:
                    logger.warning("No valid stocks with prices. Waiting before retry.")
                    time.sleep(300)  # Wait for 5 minutes before retrying
                    continue

                current_portfolio = pm.get_current_portfolio()
                logger.info(f"Current portfolio: {current_portfolio}")

                rebalance_orders = pm.calculate_rebalance_orders(current_portfolio, valid_top20)

                if rebalance_orders:
                    logger.info(f"Rebalance orders: {rebalance_orders}")
                    for order in rebalance_orders:
                        exchange = processed_top20[order['symbol']]['exchange']
                        wait_for_market_open(broker, exchange)
                        pm.execute_order(order)
                else:
                    logger.info("No rebalancing needed.")

                # Wait before the next iteration
                time.sleep(3600)  # Wait for 1 hour before the next check

            except Exception as e:
                logger.error(f"An error occurred: {e}", exc_info=True)
                time.sleep(300)  # Wait for 5 minutes before retrying

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        logger.critical(f"Critical error occurred: {e}", exc_info=True)
    finally:
        logger.info("Disconnecting from Interactive Brokers")
        broker.disconnect()


if __name__ == "__main__":
    main()