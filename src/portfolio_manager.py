from decimal import Decimal, ROUND_DOWN, InvalidOperation
import logging
from config import CONFIG

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self, ib_connection):
        self.ib_connection = ib_connection
        self.CASH_BUFFER = Decimal(str(CONFIG['trading']['cash_buffer']))
        self.ACCOUNT = CONFIG['interactive_brokers']['account']

    def get_current_portfolio(self):
        positions = self.ib_connection.get_positions()
        account_summary = self.ib_connection.get_account_summary()

        portfolio = {
            'CASH': Decimal(str(account_summary.get('cash', 0)))
        }

        for symbol, details in positions.items():
            portfolio[symbol] = {
                'shares': Decimal(str(details['shares'])),
                'price': Decimal(str(details['avgCost']))
            }

        logger.info(f"Current portfolio: {portfolio}")
        return portfolio

    def get_total_portfolio_value(self, portfolio):
        try:
            return sum(stock['shares'] * stock['price']
                       for symbol, stock in portfolio.items() if symbol != 'CASH') + portfolio['CASH']
        except InvalidOperation as e:
            logger.error(f"Error calculating total portfolio value: {e}")
            logger.debug(f"Portfolio data: {portfolio}")
            raise

    def calculate_rebalance_orders(self, current_portfolio, new_top20):
        try:
            total_value = self.get_total_portfolio_value(current_portfolio)
            target_position_value = (total_value - self.CASH_BUFFER) / Decimal('20')

            sell_orders = []
            buy_orders = []

            logger.debug(f"Current portfolio: {current_portfolio}")
            logger.debug(f"New top 20: {new_top20}")

            # Identify stocks to sell (not in new top 20)
            for symbol, details in current_portfolio.items():
                if symbol != 'CASH' and symbol not in new_top20:
                    sell_orders.append({
                        'symbol': symbol,
                        'action': 'SELL',
                        'shares': details['shares']
                    })

            # Calculate available cash after selling
            cash_after_selling = current_portfolio['CASH'] + sum(
                current_portfolio[order['symbol']]['shares'] * current_portfolio[order['symbol']]['price']
                for order in sell_orders
            )

            # Identify stocks to buy or add to
            valid_new_stocks = [symbol for symbol, details in new_top20.items() if details.get('price') is not None]
            if not valid_new_stocks:
                logger.warning("No stocks with valid price information in new Top20. Skipping buy orders.")
                return sell_orders, []

            cash_per_new_stock = (cash_after_selling - self.CASH_BUFFER) / Decimal(str(len(valid_new_stocks)))

            for symbol in valid_new_stocks:
                details = new_top20[symbol]
                price = Decimal(str(details['price']))
                if symbol not in current_portfolio or current_portfolio[symbol]['shares'] == 0:
                    # New stock to buy
                    shares_to_buy = min(
                        (cash_per_new_stock / price).quantize(Decimal('0.0001'), rounding=ROUND_DOWN),
                        (target_position_value / price).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
                    )

                    if shares_to_buy > Decimal('0'):
                        buy_orders.append({
                            'symbol': symbol,
                            'action': 'BUY',
                            'shares': shares_to_buy
                        })
                        cash_after_selling -= shares_to_buy * price

            logger.info(f"Sell orders: {sell_orders}")
            logger.info(f"Buy orders: {buy_orders}")

            return sell_orders, buy_orders

        except InvalidOperation as e:
            logger.error(f"Error in calculate_rebalance_orders: {e}")
            logger.debug(f"Current portfolio: {current_portfolio}")
            logger.debug(f"New top 20: {new_top20}")
            raise

    def execute_orders(self, orders):
        for order in orders:
            try:
                self.ib_connection.place_order(
                    symbol=order['symbol'],
                    secType='STK',
                    exchange='SMART',
                    action=order['action'],
                    quantity=float(order['shares'])  # Convert Decimal to float for IB API
                )
                logger.info(f"Executed order: {order}")
            except Exception as e:
                logger.error(f"Failed to execute order {order}: {e}")