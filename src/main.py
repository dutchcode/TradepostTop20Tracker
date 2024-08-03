import time
import logging
from config import CONFIG
from tradepost_api import TradepostAPI
from ib_connection import IBConnection
from portfolio_manager import PortfolioManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    tradepost = TradepostAPI(CONFIG['tradepost']['api_key'])
    ib_config = CONFIG['interactive_brokers']
    ib = IBConnection(ib_config['host'], ib_config['port'], ib_config['client_id'])
    pm = PortfolioManager(ib)

    try:
        ib.connect()
        logging.info("Connected to Interactive Brokers")

        while True:
            try:
                # Fetch the latest Top20 data
                top20_data = tradepost.get_top20()
                logging.info(f"Fetched Top20 data for date: {top20_data['date']}")

                # Get current portfolio
                current_portfolio = pm.get_current_portfolio()
                logging.info(f"Current portfolio: {current_portfolio}")

                # Calculate rebalance orders
                sell_orders, buy_orders = pm.calculate_rebalance_orders(current_portfolio, top20_data['constituents'])

                # Execute orders
                if sell_orders:
                    logging.info(f"Executing sell orders: {sell_orders}")
                    pm.execute_orders(sell_orders)

                if buy_orders:
                    logging.info(f"Executing buy orders: {buy_orders}")
                    pm.execute_orders(buy_orders)

                # Sleep for a day (adjust as needed)
                time.sleep(86400)  # 24 hours

            except Exception as e:
                logging.error(f"An error occurred: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying

    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        ib.disconnect()
        logging.info("Disconnected from Interactive Brokers")


if __name__ == "__main__":
    main()