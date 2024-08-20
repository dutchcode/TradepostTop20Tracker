# main.py

import logging
import time
from datetime import datetime

import pytz

from utils.import_helper import add_vendor_to_path

add_vendor_to_path()

from config import CONFIG
from tradepost_api import TradepostAPI
from broker import IBBroker
from portfolio_manager import PortfolioManager

# Set root logger to INFO
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set IBAPI logger to WARNING to reduce its output
logging.getLogger('ibapi').setLevel(logging.WARNING)

# Keep DEBUG level for your custom logger if needed
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
                price = broker.get_market_price(data['isin'], ticker, data['exchange'], data['name'])
                if price is not None:
                    prices[ticker] = price
                    logger.info(f"Got price for {ticker} ({data['name']}): {price}")
                    break
                else:
                    logger.warning(f"Failed to get price for {ticker} ({data['name']}). Retries left: {retries - 1}")
                    retries -= 1
            except Exception as e:
                logger.error(f"Failed to get price for {ticker} ({data['name']}): {e}")
                retries -= 1
            time.sleep(60)  # Wait for 1 minute before retrying

        if ticker not in prices:
            logger.error(f"Unable to get price for {ticker} ({data['name']}) after all retries. Skipping this stock.")

    return prices

def process_open_markets(broker, processed_top20):
    open_market_stocks = {}
    closed_market_stocks = {}

    for ticker, data in processed_top20.items():
        if broker.is_market_open(data['exchange']):
            open_market_stocks[ticker] = data
        else:
            closed_market_stocks[ticker] = data

    current_prices = get_current_prices(broker, open_market_stocks)

    return current_prices, closed_market_stocks

def get_unique_markets_and_times(processed_top20, broker):
    unique_markets = set(data['exchange'] for data in processed_top20.values())
    market_times = {}
    for market in unique_markets:
        next_open = broker.get_next_market_open(market)
        market_times[market] = next_open
    return market_times

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
    pm = PortfolioManager(broker, CONFIG)

    try:
        logger.info("Attempting to connect to Interactive Brokers")
        broker.connect()

        # Cancel all open orders
        broker.cancel_all_orders()
        logger.info("Cancelled all open orders")

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

                # Get unique markets and their opening times
                market_times = get_unique_markets_and_times(processed_top20, broker)

                # Display current UTC time
                logger.info(f"Current UTC time: {datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}")

                # Display markets and their opening times
                logger.info("Markets to check and their next opening times:")
                for market, open_time in market_times.items():
                    logger.info(f"{market}: {open_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

                all_prices = {}
                remaining_stocks = processed_top20

                for exchange in market_times.keys():
                    current_prices, remaining_stocks = process_open_markets(broker, remaining_stocks)
                    all_prices.update(current_prices)

                    if not remaining_stocks:
                        break

                    if current_prices:
                        # Calculate quantities and place orders for the current market
                        pm.calculate_and_execute_orders(current_prices)

                    if remaining_stocks:
                        next_market_open = min(broker.get_next_market_open(data['exchange'])
                                               for data in remaining_stocks.values())
                        wait_time = (next_market_open - datetime.now(pytz.utc)).total_seconds()
                        next_market = min(remaining_stocks.values(), key=lambda x: broker.get_next_market_open(x['exchange']))['exchange']
                        logger.info(f"Current UTC time: {datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}")
                        logger.info(f"Waiting for {next_market} market to open. Sleep time: {wait_time / 60:.2f} minutes")
                        time.sleep(min(wait_time, 3600))  # Wait for the calculated time or max 1 hour

                if not all_prices:
                    logger.warning("No valid prices available. Waiting before retry.")
                    time.sleep(300)  # Wait for 5 minutes
                    continue

                logger.debug(f"All prices: {all_prices}")

                valid_top20 = {ticker: data for ticker, data in processed_top20.items() if ticker in all_prices}
                for ticker, data in valid_top20.items():
                    data['price'] = all_prices[ticker]

                logger.debug(f"Valid Top20 data with prices: {valid_top20}")

                # After processing all markets, update the portfolio
                pm.rebalance_portfolio(valid_top20)

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