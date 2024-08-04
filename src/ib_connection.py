from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.common import BarData
import threading
import time
import logging

logger = logging.getLogger(__name__)


class IBApi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.nextorderId = None
        self.lock = threading.Lock()
        self.account_summary = {}
        self.positions = {}
        self.contract_details = {}
        self.historical_data = {}
        self.event = threading.Event()

    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.nextorderId = orderId
        logger.info(f'The next valid order id is: {self.nextorderId}')
        self.connected = True

    def error(self, reqId, errorCode, errorString):
        logger.error(f"Error. Id: {reqId} Code: {errorCode} Msg: {errorString}")

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

    def contractDetails(self, reqId, contractDetails):
        if reqId not in self.contract_details:
            self.contract_details[reqId] = []
        self.contract_details[reqId].append(contractDetails)

    def contractDetailsEnd(self, reqId):
        self.event.set()

    def historicalData(self, reqId: int, bar: BarData):
        if reqId not in self.historical_data:
            self.historical_data[reqId] = []
        self.historical_data[reqId].append(bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        self.event.set()


class IBConnection:
    def __init__(self, host, port, clientId):
        self.host = host
        self.port = port
        self.clientId = clientId
        self.ib = IBApi()
        self.ib_thread = None
        self.next_req_id = 1

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

    def get_market_price(self, isin, symbol):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.currency = "USD"
        contract.isin = isin

        req_id = self.next_req_id
        self.next_req_id += 1

        # Clear previous data
        self.ib.contract_details.pop(req_id, None)
        self.ib.historical_data.pop(req_id, None)

        # Request contract details
        self.ib.event.clear()
        self.ib.reqContractDetails(req_id, contract)

        if not self.ib.event.wait(timeout=10):
            raise TimeoutError(f"Timeout waiting for contract details for {symbol}")

        if req_id not in self.ib.contract_details or not self.ib.contract_details[req_id]:
            raise ValueError(f"Failed to get contract details for {symbol}")

        # Use the first contract detail
        contract_details = self.ib.contract_details[req_id][0]

        # Request recent historical data to get the latest price
        self.ib.event.clear()
        self.ib.reqHistoricalData(req_id, contract_details.contract, "", "1 D", "1 min", "TRADES", 1, 1, False, [])

        if not self.ib.event.wait(timeout=10):
            raise TimeoutError(f"Timeout waiting for historical data for {symbol}")

        if req_id not in self.ib.historical_data or not self.ib.historical_data[req_id]:
            raise ValueError(f"Failed to get historical data for {symbol}")

        latest_bar = self.ib.historical_data[req_id][-1]
        return float(latest_bar.close)

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
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    from config import CONFIG

    ib_config = CONFIG['interactive_brokers']
    ib = IBConnection(ib_config['host'], ib_config['port'], ib_config['client_id'])
    ib.connect()

    try:
        # Get market price for AAPL
        price = ib.get_market_price("US0378331005", "AAPL")
        logger.info(f"Current price of AAPL: {price}")

        # Place a market order for 1 share of AAPL
        order_id = ib.place_order("AAPL", "STK", "SMART", "BUY", 1)
        logger.info(f"Placed order with ID: {order_id}")

        # Get account summary and positions
        account_summary = ib.get_account_summary()
        positions = ib.get_positions()

        logger.info(f"Account Summary: {account_summary}")
        logger.info(f"Positions: {positions}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

    finally:
        # Disconnect from IB
        ib.disconnect()
        logger.info("Disconnected from Interactive Brokers")