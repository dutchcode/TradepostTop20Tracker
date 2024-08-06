# ib_connection.py

import threading
import time
import logging
from datetime import datetime, timedelta
import pytz
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
        self.symbol_search_results = []
        self.server_time = None

    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.nextorderId = orderId
        logger.info(f'The next valid order id is: {self.nextorderId}')
        self.connected.set()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        if errorCode in [2104, 2106, 2158]:
            logger.info(f"Connection info: {errorString}")
        elif errorCode == 200 and "No security definition has been found" in errorString:
            logger.warning(f"No security definition found for reqId {reqId}: {errorString}")
            self.event.set()
        elif errorCode == 200 and "Invalid exchange" in errorString:
            logger.warning(f"Invalid exchange for reqId {reqId}: {errorString}")
            self.event.set()
        elif errorCode == 10168:
            logger.info(f"Market data farm connection message: {errorString}")
        elif errorCode == 10167:
            logger.error(f"Historical Market Data Service error for reqId {reqId}: {errorString}")
            self.event.set()
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

    def symbolSamples(self, reqId: int, contractDescriptions: list):
        for contract in contractDescriptions:
            self.symbol_search_results.append({
                "symbol": contract.contract.symbol,
                "exchange": contract.contract.exchange,
                "currency": contract.contract.currency
            })
            logger.info(
                f"Symbol: {contract.contract.symbol}, Exchange: {contract.contract.exchange}, Currency: {contract.contract.currency}")
        self.event.set()

    def currentTime(self, time):
        self.server_time = time
        self.event.set()


class IBConnection:
    EXCHANGE_MAPPING = {
        "US": ("SMART", "USD"),
        "LSE": ("LSEETF", "GBP"),
        "F": ("IBIS", "EUR"),
        "KO": ("KSE", "KRW"),
        "T": ("TSE", "JPY"),
        "HK": ("SEHK", "HKD"),
    }

    def __init__(self, host, port, clientId, api_version):
        self.host = host
        self.port = port
        self.clientId = clientId
        self.api_version = api_version
        self.ib = IBApi()
        self.ib_thread = None
        self.next_req_id = 1
        self.market_hours = {
            'US': {'open': (9, 30), 'close': (16, 0), 'timezone': 'America/New_York'},
            'LSE': {'open': (8, 0), 'close': (16, 30), 'timezone': 'Europe/London'},
            'F': {'open': (9, 0), 'close': (17, 30), 'timezone': 'Europe/Berlin'},
            'KO': {'open': (9, 0), 'close': (15, 30), 'timezone': 'Asia/Seoul'},
            'T': {'open': (9, 0), 'close': (15, 0), 'timezone': 'Asia/Tokyo'},
            'HK': {'open': (9, 30), 'close': (16, 0), 'timezone': 'Asia/Hong_Kong'},
        }

    def connect(self):
        self.ib.connect(self.host, self.port, self.clientId)
        self.ib_thread = threading.Thread(target=self.run_loop, daemon=True)
        self.ib_thread.start()
        if not self.ib.connected.wait(timeout=15):
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

    def is_connected(self):
        return self.ib.isConnected()

    def ensure_connection(self):
        if not self.is_connected():
            logger.warning("IB connection lost. Attempting to reconnect...")
            self.connect()

    def set_market_data_type(self):
        self.ib.reqMarketDataType(MarketDataTypeEnum.REALTIME)

    def is_market_open(self, exchange):
        if exchange not in self.market_hours:
            logger.warning(f"Unknown exchange: {exchange}. Assuming market is open.")
            return True

        market_info = self.market_hours[exchange]
        tz = pytz.timezone(market_info['timezone'])
        now = datetime.now(tz)
        open_time = now.replace(hour=market_info['open'][0], minute=market_info['open'][1], second=0, microsecond=0)
        close_time = now.replace(hour=market_info['close'][0], minute=market_info['close'][1], second=0, microsecond=0)

        return open_time <= now <= close_time

    def is_market_opening_soon(self, exchange, minutes=30):
        if exchange not in self.market_hours:
            logger.warning(f"Unknown exchange: {exchange}. Assuming market is not opening soon.")
            return False

        market_info = self.market_hours[exchange]
        tz = pytz.timezone(market_info['timezone'])
        now = datetime.now(tz)
        open_time = now.replace(hour=market_info['open'][0], minute=market_info['open'][1], second=0, microsecond=0)

        time_until_open = open_time - now
        return timedelta(minutes=0) <= time_until_open <= timedelta(minutes=minutes)

    def wait_for_market_open(self, exchange):
        while not self.is_market_open(exchange):
            if self.is_market_opening_soon(exchange):
                logger.info(f"Market for {exchange} is opening soon. Waiting for 1 minute before checking again.")
                time.sleep(60)  # Wait for 1 minute
            else:
                logger.info(f"Market for {exchange} is closed. Waiting for 5 minutes before checking again.")
                time.sleep(300)  # Wait for 5 minutes

    def create_contract(self, symbol, secType, exchange, currency=None, isin=None):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        contract.exchange, contract.currency = self.EXCHANGE_MAPPING.get(exchange, ("SMART", "USD"))
        if currency:
            contract.currency = currency
        contract.primaryExchange = self.EXCHANGE_MAPPING.get(exchange, ("SMART", "USD"))[0]
        if isin:
            contract.isin = isin
        return contract

    def search_symbol(self, symbol, exchange):
        self.ib.symbol_search_results = []
        self.ib.event.clear()
        req_id = self.next_req_id
        self.next_req_id += 1

        self.ib.reqMatchingSymbols(req_id, symbol)

        if not self.ib.event.wait(timeout=10):
            raise TimeoutError(f"Timeout waiting for symbol search results for {symbol}")

        return self.ib.symbol_search_results

    def get_market_price(self, isin, symbol, exchange, name):
        self.wait_for_market_open(exchange)
        search_results = self.search_symbol(symbol, exchange)
        if not search_results:
            raise ValueError(f"No matching symbols found for {symbol} on {exchange}")

        contract = self.create_contract(symbol, "STK", exchange, isin=isin)

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
        self.wait_for_market_open(exchange)
        contract = self.create_contract(symbol, secType, exchange)

        order = Order()
        order.action = action
        order.orderType = "MKT"
        order.totalQuantity = float(quantity)  # Convert Decimal to float
        order.cashQty = None

        with self.ib.lock:
            orderId = self.ib.nextorderId
            self.ib.nextorderId += 1

        try:
            self.ib.placeOrder(orderId, contract, order)
            logger.info(f"Order placed: {symbol} {action} {quantity}")
            return orderId
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    def get_account_summary(self):
        self.ib.account_summary = {}
        self.ib.reqAccountSummary(1, "All", "TotalCashValue,NetLiquidation")
        time.sleep(1)
        return self.ib.account_summary

    def get_positions(self):
        self.ib.positions = {}
        self.ib.reqPositions()
        time.sleep(1)
        return self.ib.positions

    def cancel_all_orders(self):
        self.ib.reqGlobalCancel()

    def get_ib_server_time(self):
        self.ib.event.clear()
        self.ib.reqCurrentTime()
        if not self.ib.event.wait(timeout=10):
            raise TimeoutError("Timeout waiting for server time")
        return self.ib.server_time

    def validate_contract(self, contract):
        req_id = self.next_req_id
        self.next_req_id += 1
        self.ib.event.clear()
        self.ib.reqContractDetails(req_id, contract)
        if not self.ib.event.wait(timeout=10):
            raise TimeoutError(f"Timeout waiting for contract details for {contract.symbol}")
        if req_id not in self.ib.contract_details or not self.ib.contract_details[req_id]:
            raise ValueError(f"Invalid contract: {contract.symbol}")
        return self.ib.contract_details[req_id][0].contract