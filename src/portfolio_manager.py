# portfolio_manager.py

import logging
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from utils.import_helper import add_vendor_to_path

add_vendor_to_path()

from config import CONFIG

logger = logging.getLogger(__name__)


class PortfolioManager:
    def __init__(self, broker):
        self.broker = broker
        self.CASH_BUFFER = Decimal(str(CONFIG.get('trading.cash_buffer', '50')))
        self.ACCOUNT = CONFIG.get('interactive_brokers.account')
        self.MAX_POSITION_SIZE = Decimal(
            str(CONFIG.get('trading.max_position_size', '0.1')))  # 10% of portfolio by default

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
                            'shares': shares_to_buy
                        })
                        cash_after_selling -= shares_to_buy * price
                elif current_value > target_value:
                    shares_to_sell = ((current_value - target_value) / price).quantize(Decimal('0.0001'),
                                                                                       rounding=ROUND_DOWN)
                    if shares_to_sell > Decimal('0'):
                        sell_orders.append({
                            'symbol': symbol,
                            'action': 'SELL',
                            'shares': shares_to_sell
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
            if not self.broker.is_market_open(exchange):
                logger.warning(f"Market is closed for {order['symbol']}. Order will be queued: {order}")
                # Here you could implement a queue for orders to be executed when the market opens
                return

            order_id = self.broker.place_order(
                symbol=order['symbol'],
                secType='STK',
                exchange='SMART',
                action=order['action'],
                quantity=float(order['quantity'])
            )
            if order_id is not None:
                logger.info(f"Executed order: {order}, Order ID: {order_id}")
            else:
                logger.error(f"Failed to execute order: {order}. Order ID is None.")
        except Exception as e:
            logger.error(f"Error executing order {order}: {e}", exc_info=True)

    def calculate_and_execute_orders(self, current_prices, cash_available):
        try:
            total_value = sum(current_prices.values())
            target_value_per_stock = min(cash_available / len(current_prices), total_value * self.MAX_POSITION_SIZE)

            queued_orders = []
            for symbol, price in current_prices.items():
                quantity = int(target_value_per_stock / price)
                if quantity > 0:
                    order = {
                        'symbol': symbol,
                        'action': 'BUY',
                        'quantity': quantity,
                        'price': price
                    }
                    exchange = self.broker.EXCHANGE_MAPPING.get(symbol, ('SMART', 'USD'))[0]
                    if self.broker.is_market_open(exchange):
                        self.execute_order(order)
                    else:
                        queued_orders.append(order)
                        logger.info(f"Market closed for {symbol}. Order queued: {order}")

            if queued_orders:
                logger.info(f"Queued orders for later execution: {queued_orders}")
                # Here you could implement a mechanism to execute these orders when the market opens

            logger.info(f"Remaining cash after order calculations: {cash_available}")
            return cash_available
        except Exception as e:
            logger.error(f"Error calculating and executing orders: {e}", exc_info=True)
            raise

    def rebalance_portfolio(self, current_portfolio, new_top20):
        try:
            total_value = self.get_total_portfolio_value(current_portfolio)
            cash_available = current_portfolio['CASH']

            # Sell stocks not in new top 20
            for symbol, details in current_portfolio.items():
                if symbol != 'CASH' and symbol not in new_top20:
                    order = {
                        'symbol': symbol,
                        'action': 'SELL',
                        'quantity': details['shares']
                    }
                    self.execute_order(order)
                    cash_available += details['shares'] * details['price']

            # Buy or adjust positions for stocks in new top 20
            remaining_cash = self.calculate_and_execute_orders(
                {symbol: details['price'] for symbol, details in new_top20.items()},
                cash_available
            )

            logger.info("Portfolio rebalancing completed")
            logger.info(f"Remaining cash: {remaining_cash}")
        except Exception as e:
            logger.error(f"Error during portfolio rebalancing: {e}")

    def get_portfolio_summary(self):
        try:
            portfolio = self.get_current_portfolio()
            total_value = self.get_total_portfolio_value(portfolio)

            summary = {
                'total_value': total_value,
                'cash': portfolio['CASH'],
                'positions': {}
            }

            for symbol, details in portfolio.items():
                if symbol != 'CASH':
                    position_value = details['shares'] * details['price']
                    summary['positions'][symbol] = {
                        'shares': details['shares'],
                        'price': details['price'],
                        'value': position_value,
                        'weight': (position_value / total_value).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
                    }

            logger.info(f"Portfolio summary: {summary}")
            return summary
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            raise

    def check_risk_limits(self):
        try:
            summary = self.get_portfolio_summary()

            for symbol, details in summary['positions'].items():
                if details['weight'] > self.MAX_POSITION_SIZE:
                    logger.warning(f"Position {symbol} exceeds maximum allowed size: {details['weight']}")

            cash_ratio = summary['cash'] / summary['total_value']
            if cash_ratio < Decimal('0.05'):  # Less than 5% cash
                logger.warning(f"Cash position is low: {cash_ratio:.2%}")

            logger.info("Risk limit check completed")
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")