from decimal import Decimal, ROUND_DOWN


class PortfolioManager:
    def __init__(self, ib_connection):
        self.ib_connection = ib_connection
        self.CASH_BUFFER = 50  # Buffer in USD/EUR for transaction costs

    def get_current_portfolio(self):
        positions = self.ib_connection.get_positions()
        account_summary = self.ib_connection.get_account_summary()

        portfolio = {
            'CASH': account_summary.get('cash', 0)
        }

        for symbol, details in positions.items():
            portfolio[symbol] = {
                'shares': details['shares'],
                'price': details['avgCost']
            }

        return portfolio

    def get_total_portfolio_value(self, portfolio):
        return sum(stock['shares'] * stock['price'] for stock in portfolio.values() if stock != 'CASH') + portfolio[
            'CASH']

    def calculate_rebalance_orders(self, current_portfolio, new_top20):
        total_value = self.get_total_portfolio_value(current_portfolio)
        target_position_value = Decimal(total_value) / 20  # Value for each position if equally distributed

        sell_orders = []
        buy_orders = []

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
        for symbol in new_top20:
            if symbol not in current_portfolio or current_portfolio[symbol]['shares'] == 0:
                # New stock to buy
                cash_to_use = min(cash_after_selling - self.CASH_BUFFER, target_position_value)
                shares_to_buy = int(
                    (cash_to_use / Decimal(new_top20[symbol]['price'])).quantize(Decimal('1.'), rounding=ROUND_DOWN))

                if shares_to_buy > 0:
                    buy_orders.append({
                        'symbol': symbol,
                        'action': 'BUY',
                        'shares': shares_to_buy
                    })
                    cash_after_selling -= shares_to_buy * Decimal(new_top20[symbol]['price'])

        return sell_orders, buy_orders

    def execute_orders(self, orders):
        for order in orders:
            self.ib_connection.place_order(
                symbol=order['symbol'],
                secType='STK',
                exchange='SMART',
                action=order['action'],
                quantity=order['shares']
            )


# Example usage
if __name__ == "__main__":
    from ib_connection import IBConnection
    from config import CONFIG

    ib_config = CONFIG['interactive_brokers']
    ib = IBConnection(ib_config['host'], ib_config['port'], ib_config['client_id'])
    ib.connect()

    pm = PortfolioManager(ib)
    current_portfolio = pm.get_current_portfolio()
    print("Current Portfolio:", current_portfolio)

    # Mock new Top 20 data
    mock_new_top20 = {
        'AAPL': {'price': 155},
        'MSFT': {'price': 300},
        'AMZN': {'price': 3300},
        # ... (add more stocks to make it 20)
    }

    sell_orders, buy_orders = pm.calculate_rebalance_orders(current_portfolio, mock_new_top20)

    print("Sell Orders:", sell_orders)
    print("Buy Orders:", buy_orders)

    # Uncomment these lines to actually execute the orders
    # pm.execute_orders(sell_orders)
    # pm.execute_orders(buy_orders)

    ib.disconnect()