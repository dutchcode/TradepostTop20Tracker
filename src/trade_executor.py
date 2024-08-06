# trade_executor.py

import logging

logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self, ib_connection):
        self.ib_connection = ib_connection

    def execute_order(self, order):
        try:
            order_id = self.ib_connection.place_order(
                symbol=order['symbol'],
                secType='STK',
                exchange=order.get('exchange', 'SMART'),
                action=order['action'],
                quantity=float(order['shares'])
            )
            if order_id:
                logger.info(f"Executed order: {order}")
            else:
                logger.error(f"Failed to execute order: {order}")
        except Exception as e:
            logger.error(f"Error executing order {order}: {e}")