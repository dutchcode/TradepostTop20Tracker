# trade_executor.py

import logging

logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self, ib_connection):
        self.ib_connection = ib_connection

    def execute_orders(self, orders):
        for order in orders:
            try:
                self.ib_connection.place_order(
                    symbol=order['symbol'],
                    secType='STK',
                    exchange='SMART',
                    action=order['action'],
                    quantity=order['shares']  # This can now be a fractional number
                )
                logger.info(f"Executed order: {order}")
            except Exception as e:
                logger.error(f"Failed to execute order {order}: {e}")