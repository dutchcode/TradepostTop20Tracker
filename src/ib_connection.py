import threading
import time
import logging
from utils.import_helper import add_vendor_to_path

add_vendor_to_path()
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.common import BarData, MarketDataTypeEnum

logger = logging.getLogger(__name__)


class IBApi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.connected = threading.Event()
        self.nextorderId = None
        self.lock = threading.Lock()
        self.account_summary = {}
        self.positions = {}
        self.contract_details = {}
        self.historical_data = {}
        self.event = threading.Event()
        self.last_price = None

    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.nextorderId = orderId
        logger.info(f'The next valid order id is: {self.nextorderId}')
        self.connected.set()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        if errorCode in [2104, 2106, 2158]:  # Market data connection messages
            logger.info(f"Connection info: {errorString}")
        elif errorCode == 200 and "No security definition has been found" in errorString:
            logger.warning(f"No security definition found for reqId {reqId}: {errorString}")
            self.event.set()  # Set the event to prevent timeout
        elif errorCode == 10168:  # Market data farm connection is inactive but should be available upon demand
            logger.info(f"Market data farm connection message: {errorString}")
        elif errorCode == 10167:  # Historical Market Data Service error
            logger.error(f"Historical Market Data Service error for reqId {reqId}: {errorString}")
            self.event.set()  # Set the event to prevent timeout
        else:
            logger.error(f"Error. Id: {reqId} Code: {errorCode} Msg: {errorString}")

        if advancedOrderRejectJson:
            logger.error(f"Advanced order reject JSON: {advancedOrderRejectJson}")

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

    def tickPrice(self, reqId, tickType, price, attrib):
        logger.info(f"TickPrice. ReqId: {reqId}, TickType: {tickType}, Price: {price}")
        if tickType == 4:  # Last price
            self.last_price = price
        self.event.set()


class IBConnection:
    EXCHANGE_MAPPING = {
        "US": ("SMART", "USD"),  # United States
        "F": ("IBIS", "EUR"),  # Frankfurt
        "KO": ("KSE", "KRW"),  # Korea Stock Exchange
        "L": ("LSE", "GBP"),  # London Stock Exchange
        "T": ("TSE", "JPY"),  # Tokyo Stock Exchange
        "HK": ("SEHK", "HKD"),  # Hong Kong Stock Exchange
        # Add more exchanges as needed
    }

    def __init__(self, host, port, clientId, api_version):
        self.host = host
        self.port = port
        self.clientId = clientId
        self.api_version = api_version
        self.ib = IBApi()
        self.ib_thread = None
        self.next_req_id = 1

    def connect(self):
        self.ib.connect(self.host, self.port, self.clientId)
        self.ib_thread = threading.Thread(target=self.run_loop, daemon=True)
        self.ib_thread.start()
        if not self.ib.connected.wait(timeout=15):  # Increased timeout to 15 seconds
            raise TimeoutError("Failed to connect to Interactive Brokers")
        logger.info("Successfully connected to Interactive Brokers")

    def disconnect(self):
        if self.ib.isConnected():
            self.ib.disconnect()
        if self.ib_thread:
            self.ib_thread.join(timeout=5)
        logger.info("Disconnected from Interactive Brokers")

    def run_loop(self):
        try:
            self.ib.run()
        except Exception as e:
            logger.error(f"Error in IB connection thread: {e}")
        finally:
            self.ib.connected.clear()

    def get_market_price(self, isin, symbol, exchange, name):
        contract = Contract()
        contract.secType = "STK"
        contract.isin = isin
        contract.symbol = symbol

        contract.exchange, contract.currency = self.EXCHANGE_MAPPING.get(exchange, ("SMART", "USD"))

        logger.info(
            f"Requesting data for: ISIN={isin}, Symbol={symbol}, Exchange={contract.exchange}, Currency={contract.currency}, Name={name}")

        req_id = self.next_req_id
        self.next_req_id += 1

        self.ib.contract_details.pop(req_id, None)
        self.ib.historical_data.pop(req_id, None)

        self.ib.event.clear()
        self.ib.reqContractDetails(req_id, contract)

        if not self.ib.event.wait(timeout=10):
            raise TimeoutError(
                f"Timeout waiting for contract details for ISIN: {isin}, Symbol: {symbol}, Exchange: {exchange}, Name: {name}")

        if req_id not in self.ib.contract_details or not self.ib.contract_details[req_id]:
            raise ValueError(
                f"Failed to get contract details for ISIN: {isin}, Symbol: {symbol}, Exchange: {exchange}, Name: {name}")

        contract_details = self.ib.contract_details[req_id][0]
        logger.info(f"Found contract: {contract_details.contract}")

        self.ib.event.clear()
        self.ib.reqHistoricalData(req_id, contract_details.contract, "", "1 D", "1 min", "TRADES", 1, 1, False, [])

        if not self.ib.event.wait(timeout=10):
            logger.warning(f"Timeout waiting for historical data. Falling back to market data for {symbol}")
            return self.get_market_data_price(contract_details.contract)

        if req_id not in self.ib.historical_data or not self.ib.historical_data[req_id]:
            logger.warning(f"No historical data received. Falling back to market data for {symbol}")
            return self.get_market_data_price(contract_details.contract)

        latest_bar = self.ib.historical_data[req_id][-1]
        return float(latest_bar.close)

    def get_market_data_price(self, contract):
        req_id = self.next_req_id
        self.next_req_id += 1

        self.ib.event.clear()
        self.ib.reqMktData(req_id, contract, "", False, False, [])

        if not self.ib.event.wait(timeout=5):
            raise TimeoutError(f"Timeout waiting for market data for {contract.symbol}")

        self.ib.cancelMktData(req_id)

        if self.ib.last_price is not None:
            return self.ib.last_price
        else:
            raise ValueError(f"Failed to get market data for {contract.symbol}")

    def place_order(self, symbol, secType, exchange, action, quantity):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        contract.exchange = exchange
        contract.currency = "USD"

        order = Order()
        order.action = action
        order.orderType = "MKT"

        if isinstance(quantity, float) and not quantity.is_integer():
            order.totalQuantity = quantity
            order.cashQty = None
        else:
            order.totalQuantity = int(quantity)

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