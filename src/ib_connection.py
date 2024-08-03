from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import threading
import time

class IBApi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.nextorderId = None
        self.lock = threading.Lock()
        self.account_summary = {}
        self.positions = {}

    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.nextorderId = orderId
        print('The next valid order id is: ', self.nextorderId)
        self.connected = True

    def error(self, reqId, errorCode, errorString):
        print("Error. Id:", reqId, "Code:", errorCode, "Msg:", errorString)

    def orderStatus(self, orderId, status, filled, remaining, avgFullPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        print("OrderStatus. Id:", orderId, "Status:", status, "Filled:", filled, "Remaining:", remaining, "AvgFullPrice:", avgFullPrice)

    def openOrder(self, orderId, contract, order, orderState):
        print("OpenOrder. ID:", orderId, contract.symbol, contract.secType, "@", contract.exchange, ":", order.action, order.orderType, order.totalQuantity, orderState.status)

    def execDetails(self, reqId, contract, execution):
        print("ExecDetails. ", reqId, contract.symbol, contract.secType, contract.currency, execution.execId, execution.orderId, execution.shares, execution.lastLiquidity)

    def accountSummary(self, reqId, account, tag, value, currency):
        if tag == "TotalCashValue":
            self.account_summary["cash"] = float(value)
        elif tag == "NetLiquidation":
            self.account_summary["net_liquidation"] = float(value)

    def position(self, account, contract, position, avgCost):
        self.positions[contract.symbol] = {
            "shares": position,
            "avgCost": avgCost
        }

class IBConnection:
    def __init__(self, host, port, clientId):
        self.host = host
        self.port = port
        self.clientId = clientId
        self.ib = IBApi()
        self.ib_thread = None

    def connect(self):
        self.ib.connect(self.host, self.port, self.clientId)
        self.ib_thread = threading.Thread(target=self.run_loop, daemon=True)
        self.ib_thread.start()
        while not self.ib.connected:
            time.sleep(0.1)

    def disconnect(self):
        self.ib.disconnect()
        if self.ib_thread:
            self.ib_thread.join()

    def run_loop(self):
        self.ib.run()

    def place_order(self, symbol, secType, exchange, action, quantity):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        contract.exchange = exchange
        contract.currency = "USD"

        order = Order()
        order.action = action
        order.totalQuantity = quantity
        order.orderType = "MKT"

        with self.ib.lock:
            orderId = self.ib.nextorderId
            self.ib.nextorderId += 1

        self.ib.placeOrder(orderId, contract, order)
        return orderId

    def get_account_summary(self):
        self.ib.account_summary = {}
        self.ib.reqAccountSummary(1, "All", "TotalCashValue,NetLiquidation")
        time.sleep(1)  # Wait for the data to be received
        return self.ib.account_summary

    def get_positions(self):
        self.ib.positions = {}
        self.ib.reqPositions()
        time.sleep(1)  # Wait for the data to be received
        return self.ib.positions

# Example usage
if __name__ == "__main__":
    from config import CONFIG

    ib_config = CONFIG['interactive_brokers']
    ib = IBConnection(ib_config['host'], ib_config['port'], ib_config['client_id'])
    ib.connect()

    # Place a market order for 100 shares of AAPL
    order_id = ib.place_order("AAPL", "STK", "SMART", "BUY", 100)
    print(f"Placed order with ID: {order_id}")

    # Get account summary and positions
    account_summary = ib.get_account_summary()
    positions = ib.get_positions()

    print("Account Summary:", account_summary)
    print("Positions:", positions)

    # Keep the script running to receive callbacks
    time.sleep(10)

    ib.disconnect()