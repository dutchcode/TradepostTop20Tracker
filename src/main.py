import time
import logging
from utils.import_helper import add_vendor_to_path
add_vendor_to_path()
from config import CONFIG
from tradepost_api import TradepostAPI
from ib_connection import IBConnection
from portfolio_manager import PortfolioManager
from datetime import datetime, timedelta

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
                price = ib.get_market_price(data['isin'], ticker, data['exchange'], data['name'])
                prices[ticker] = price
                logger.info(f"Got price for {ticker} ({data['name']}): {price}")
                break
            except TimeoutError as e:
                logger.warning(f"Timeout getting price for {ticker} ({data['name']}). Retries left: {retries - 1}")
                retries -= 1
            except Exception as e:
                logger.error(f"Failed to get price for {ticker} ({data['name']}): {e}")
                retries -= 1
            time.sleep(1)  # Add a small delay between retries

        if ticker not in prices:
            logger.error(f"Unable to get price for {ticker} ({data['name']}) after all retries")

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

    retry_delay = 300  # 5 minutes
    max_retries = 3

    try:
        logger.info("Testing TradepostAPI connection...")
        try:
            top20_data = tradepost.get_top20()
            logger.info("Successfully fetched Top20 data")
            logger.debug(f"Top20 data: {top20_data}")
        except Exception as e:
            logger.error(f"Failed to fetch Top20 data: {e}")
            return  # Exit if we can't connect to Tradepost API

        logger.info("Attempting to connect to Interactive Brokers")
        try:
            ib.connect()
        except TimeoutError as e:
            logger.error(f"Failed to connect to Interactive Brokers: {e}")
            return  # Exit if we can't connect to IB
        except Exception as e:
            logger.error(f"An error occurred while connecting to Interactive Brokers: {e}")
            return  # Exit if we can't connect to IB

        while True:
            retries = 0
            while retries < max_retries:
                try:
                    if not ib.ib.isConnected():
                        logger.error("Lost connection to Interactive Brokers. Attempting to reconnect...")
                        ib.connect()

                    top20_data = tradepost.get_top20()
                    logger.info(f"Fetched Top20 data for date: {top20_data['date']}")

                    processed_top20 = process_top20_data(top20_data)
                    logger.debug(f"Processed Top20 data: {processed_top20}")

                    current_prices = get_current_prices(ib, processed_top20)
                    logger.debug(f"Current prices: {current_prices}")

                    for ticker, data in processed_top20.items():
                        if ticker in current_prices:
                            data['price'] = current_prices[ticker]

                    current_portfolio = pm.get_current_portfolio()
                    logger.info(f"Current portfolio: {current_portfolio}")

                    sell_orders, buy_orders = pm.calculate_rebalance_orders(current_portfolio, processed_top20)

                    if sell_orders:
                        logger.info(f"Executing sell orders: {sell_orders}")
                        pm.execute_orders(sell_orders)

                    if buy_orders:
                        logger.info(f"Executing buy orders: {buy_orders}")
                        pm.execute_orders(buy_orders)

                    time.sleep(1)

                    break  # Exit the retry loop if successful
                except Exception as e:
                    logger.error(f"An error occurred: {e}")
                    retries += 1
                    if retries < max_retries:
                        logger.info(f"Retrying in {retry_delay} seconds... (Attempt {retries}/{max_retries})")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Max retries reached. Skipping this iteration.")

            now = datetime.now()
            next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            sleep_seconds = (next_run - now).total_seconds()

            logger.info(f"Sleeping until next trading day ({next_run.strftime('%Y-%m-%d')})")
            time.sleep(sleep_seconds)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Shutting down...")
    except Exception as e:
        logger.critical(f"Critical error occurred: {e}")
    finally:
        logger.info("Disconnecting from Interactive Brokers")
        ib.disconnect()

if __name__ == "__main__":
    main()