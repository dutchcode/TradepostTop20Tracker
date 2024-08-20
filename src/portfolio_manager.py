# portfolio_manager.py

import logging
from decimal import Decimal, ROUND_DOWN, InvalidOperation

logger = logging.getLogger(__name__)


class PortfolioManager:
    def __init__(self, broker, config):
        self.broker = broker
        self.CASH_BUFFER = Decimal(str(config.get('trading.cash_buffer', '50')))
        self.ACCOUNT = config.get('interactive_brokers.account')
        self.MAX_POSITION_SIZE = Decimal(str(config.get('trading.max_position_size', '0.3')))
        self.MAX_ORDER_SIZE = config.get('trading.max_order_size', 50000)
        self.SELL_ORDER_CHECK_INTERVAL = 60
        self.SELL_ORDER_TIMEOUT = 3600

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
            cash = current_portfolio['CASH']
            target_position_value = min((total_value - self.CASH_BUFFER) / Decimal('20'),
                                        total_value * self.MAX_POSITION_SIZE)

            sell_orders = []
            buy_orders = []

            logger.debug(f"Current portfolio: {current_portfolio}")
            logger.debug(f"New top 20: {new_top20}")
            logger.info(f"Total portfolio value: {total_value}")
            logger.info(f"Current cash: {cash}")
            logger.info(f"Target position value: {target_position_value}")

            # Identify stocks to sell (not in new top 20 or exceeding max position size)
            for symbol, details in current_portfolio.items():
                if symbol != 'CASH':
                    current_value = details['shares'] * details['price']
                    if symbol not in new_top20:
                        logger.info(f"Selling {symbol} (not in new top 20): {details['shares']} shares")
                        sell_orders.append({
                            'symbol': symbol,
                            'action': 'SELL',
                            'shares': details['shares'],
                            'orderType': 'MKT'
                        })
                    elif current_value > target_position_value * self.MAX_POSITION_SIZE:
                        shares_to_sell = ((current_value - target_position_value * self.MAX_POSITION_SIZE) / details[
                            'price']).quantize(Decimal('1'), rounding=ROUND_DOWN)
                        if shares_to_sell > 0:
                            logger.info(
                                f"Selling excess shares of {symbol}: {shares_to_sell} shares (current value: {current_value}, max allowed: {target_position_value * self.MAX_POSITION_SIZE})")
                            sell_orders.append({
                                'symbol': symbol,
                                'action': 'SELL',
                                'shares': shares_to_sell,
                                'orderType': 'MKT'
                            })

            # Calculate available cash after selling
            cash_after_selling = cash + sum(
                current_portfolio[order['symbol']]['price'] * order['shares']
                for order in sell_orders
            )

            logger.info(f"Cash available after selling: {cash_after_selling}")

            for symbol, details in new_top20.items():
                price = Decimal(str(details['price']))
                current_shares = current_portfolio.get(symbol, {}).get('shares', Decimal('0'))
                current_value = current_shares * price

                if current_value < target_position_value * Decimal('0.98'):
                    shares_to_buy = ((target_position_value - current_value) / price).quantize(Decimal('1'),
                                                                                               rounding=ROUND_DOWN)
                    if shares_to_buy > 0:
                        if cash_after_selling >= price:
                            actual_shares_to_buy = min(shares_to_buy, cash_after_selling // price)
                            limit_price = (price * Decimal('1.02')).quantize(Decimal('0.01'),
                                                                             rounding=ROUND_DOWN)  # 2% above current price
                            logger.info(
                                f"Buying {symbol}: {actual_shares_to_buy} shares at limit price {limit_price} (current price: {price})")
                            buy_orders.append({
                                'symbol': symbol,
                                'action': 'BUY',
                                'shares': actual_shares_to_buy,
                                'orderType': 'LMT',
                                'limit_price': limit_price
                            })
                            cash_after_selling -= actual_shares_to_buy * price
                        else:
                            logger.warning(
                                f"Not enough cash to buy even one share of {symbol}. Share price: {price}, Available cash: {cash_after_selling}")
                else:
                    logger.info(
                        f"Skipping {symbol}. Current value ({current_value}) exceeds 98% of target ({target_position_value * Decimal('0.98')}).")

            logger.info(f"Remaining cash after order calculations: {cash_after_selling}")
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

            remaining_shares = order['shares']
            while remaining_shares > 0:
                chunk_size = min(remaining_shares, self.MAX_ORDER_SIZE)

                order_id = self.broker.place_order(
                    symbol=order['symbol'],
                    secType='STK',
                    exchange='SMART',
                    action=order['action'],
                    quantity=int(chunk_size),
                    order_type=order['orderType']
                )

                if order_id is not None:
                    logger.info(
                        f"Executed order chunk: {order['symbol']} {order['action']} {chunk_size}, Order ID: {order_id}")
                else:
                    logger.error(
                        f"Failed to execute order chunk: {order['symbol']} {order['action']} {chunk_size}. Order ID is None.")

                remaining_shares -= chunk_size

            logger.info(f"Completed execution of order: {order}")
        except Exception as e:
            logger.error(f"Error executing order {order}: {e}", exc_info=True)

    def rebalance_portfolio(self, new_top20):
        try:
            current_portfolio = self.get_current_portfolio()
            sell_orders, buy_orders = self.calculate_rebalance_orders(current_portfolio, new_top20)

            # Execute sell orders first
            for order in sell_orders:
                if order['shares'] > 0:
                    self.execute_order(order)
                else:
                    logger.warning(f"Skipping sell order with zero shares: {order}")

            # Then execute buy orders
            for order in buy_orders:
                if order['shares'] > 0:
                    self.execute_order(order)
                else:
                    logger.warning(f"Skipping buy order with zero shares: {order}")

            logger.info("Portfolio rebalancing completed")
        except Exception as e:
            logger.error(f"Error rebalancing portfolio: {e}", exc_info=True)
            raise

    def calculate_and_execute_orders(self, current_prices):
        try:
            current_portfolio = self.get_current_portfolio()
            total_value = self.get_total_portfolio_value(current_portfolio)
            cash_available = current_portfolio['CASH'] - self.CASH_BUFFER

            target_value_per_stock = min(cash_available / len(current_prices),
                                         total_value * self.MAX_POSITION_SIZE)

            for symbol, price in current_prices.items():
                current_shares = current_portfolio.get(symbol, {}).get('shares', Decimal('0'))
                current_value = current_shares * Decimal(str(price))

                if current_value < target_value_per_stock * Decimal('0.98'):
                    shares_to_buy = ((target_value_per_stock - current_value) / Decimal(str(price))).quantize(
                        Decimal('1'),
                        rounding=ROUND_DOWN)
                    if shares_to_buy > 0:
                        order = {
                            'symbol': symbol,
                            'action': 'BUY',
                            'shares': shares_to_buy,
                            'orderType': 'MKT'
                        }
                        self.execute_order(order)
                        cash_available -= shares_to_buy * Decimal(str(price))
                    else:
                        logger.info(
                            f"No need to buy {symbol}. Current value ({current_value}) is close to target ({target_value_per_stock}).")
                else:
                    logger.info(
                        f"Skipping {symbol}. Current value ({current_value}) exceeds 98% of target ({target_value_per_stock * Decimal('0.98')}).")

            logger.info(f"Remaining cash after order calculations: {cash_available}")
        except Exception as e:
            logger.error(f"Error calculating and executing orders: {e}", exc_info=True)
            raise