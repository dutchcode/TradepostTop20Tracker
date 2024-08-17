# portfolio_manager.py

import logging
from decimal import Decimal, ROUND_DOWN, InvalidOperation

logger = logging.getLogger(__name__)


class PortfolioManager:
    def __init__(self, broker, config):
        self.broker = broker
        self.CASH_BUFFER = Decimal(str(config.get('trading.cash_buffer', '50')))
        self.ACCOUNT = config.get('interactive_brokers.account')
        self.MAX_POSITION_SIZE = Decimal(
            str(config.get('trading.max_position_size', '0.3')))  # 30% of portfolio by default
        self.SELL_ORDER_CHECK_INTERVAL = 60  # Check sell order status every 60 seconds
        self.SELL_ORDER_TIMEOUT = 3600  # Wait for a maximum of 1 hour for sell orders to complete

    def get_current_portfolio(self):
        try:
            positions = self.broker.get_positions()
            account_summary = self.broker.get_account_summary()

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
        except Exception as e:
            logger.error(f"Error getting current portfolio: {e}")
            raise

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
            target_position_value = min((total_value - self.CASH_BUFFER) / Decimal('20'),
                                        total_value * self.MAX_POSITION_SIZE)

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
                        'shares': details['shares'],
                        'orderType': 'LMT',
                        'lmtPrice': details['price'] * Decimal('0.99')  # Set limit price 1% below current price
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

            for symbol in valid_new_stocks:
                details = new_top20[symbol]
                price = Decimal(str(details['price']))
                current_shares = current_portfolio.get(symbol, {}).get('shares', Decimal('0'))
                current_value = current_shares * price
                target_value = min(target_position_value, cash_after_selling / len(valid_new_stocks))

                if current_value < target_value:
                    shares_to_buy = ((target_value - current_value) / price).quantize(Decimal('0.0001'),
                                                                                      rounding=ROUND_DOWN)
                    if shares_to_buy > Decimal('0'):
                        buy_orders.append({
                            'symbol': symbol,
                            'action': 'BUY',
                            'shares': shares_to_buy,
                            'orderType': 'LMT',
                            'lmtPrice': price * Decimal('1.01')  # Set limit price 1% above current price
                        })
                        cash_after_selling -= shares_to_buy * price
                elif current_value > target_value:
                    shares_to_sell = ((current_value - target_value) / price).quantize(Decimal('0.0001'),
                                                                                       rounding=ROUND_DOWN)
                    if shares_to_sell > Decimal('0'):
                        sell_orders.append({
                            'symbol': symbol,
                            'action': 'SELL',
                            'shares': shares_to_sell,
                            'orderType': 'LMT',
                            'lmtPrice': price * Decimal('0.99')  # Set limit price 1% below current price
                        })
                        cash_after_selling += shares_to_sell * price

            logger.info(f"Sell orders: {sell_orders}")
            logger.info(f"Buy orders: {buy_orders}")

            return sell_orders, buy_orders

        except InvalidOperation as e:
            logger.error(f"Error in calculate_rebalance_orders: {e}")
            logger.debug(f"Current portfolio: {current_portfolio}")
            logger.debug(f"New top 20: {new_top20}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in calculate_rebalance_orders: {e}")
            raise

    def execute_order(self, order):
        try:
            exchange = self.broker.EXCHANGE_MAPPING.get(order['symbol'], ('SMART', 'USD'))[0]
            next_market_open = self.broker.get_next_market_open(exchange)

            order_id = self.broker.place_order(
                symbol=order['symbol'],
                secType='STK',
                exchange='SMART',
                action=order['action'],
                quantity=float(order['shares']),
                order_type=order['orderType'],
                limit_price=float(order['lmtPrice']),
                tif='GTC'
            )

            if order_id is not None:
                logger.info(f"Order placed: {order},
