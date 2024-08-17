# broker.py

import logging
import threading
import time

import exchange_calendars as xcals
import pandas as pd

from utils.import_helper import add_vendor_to_path

add_vendor_to_path()
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.common import BarData

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


class IBBroker:
    # Mapping all possible exchange codes coming in from Tradepost.ai
    EXCHANGE_MAPPING = {
        "US": ("SMART", "USD"),
        "LSE": ("LSEETF", "GBP"),
        "TO": ("TSX", "CAD"),
        "V": ("VENTURE", "CAD"),
        "NEO": ("OMEGA", "CAD"),
        "BE": ("SBF", "EUR"),
        "HM": ("SBF", "EUR"),
        "XETRA": ("IBIS", "EUR"),
        "DU": ("SBF", "EUR"),
        "HA": ("SBF", "EUR"),
        "MU": ("SBF", "EUR"),
        "STU": ("SBF", "EUR"),
        "F": ("IBIS", "EUR"),
        "LU": ("SBF", "EUR"),
        "VI": ("VSE", "EUR"),
        "PA": ("SBF", "EUR"),
        "BR": ("EBR", "EUR"),
        "MC": ("SN", "EUR"),
        "SW": ("VIRTX", "CHF"),
        "LS": ("BVL", "EUR"),
        "AS": ("AEB", "EUR"),
        "IC": ("ICEX", "ISK"),
        "IR": ("ISE", "EUR"),
        "HE": ("HEX", "EUR"),
        "OL": ("OSE", "NOK"),
        "CO": ("CSE", "DKK"),
        "ST": ("SFB", "SEK"),
        "VFEX": ("VFEX", "ZWL"),
        "XZIM": ("ZSE", "ZWL"),
        "LUSE": ("LUSE", "ZMW"),
        "USE": ("USE", "UGX"),
        "DSE": ("DSE", "TZS"),
        "PR": ("PRA", "CZK"),
        "RSE": ("RSE", "RWF"),
        "XBOT": ("XBOT", "BWP"),
        "EGX": ("EGX", "EGP"),
        "XNSA": ("XNSA", "NGN"),
        "GSE": ("GSE", "GHS"),
        "MSE": ("MSE", "MWK"),
        "BRVM": ("BRVM", "XOF"),
        "XNAI": ("XNAI", "KES"),
        "BC": ("BCAS", "MAD"),
        "SEM": ("SEM", "MUR"),
        "TA": ("TASE", "ILS"),
        "KQ": ("KOSDAQ", "KRW"),
        "KO": ("KSE", "KRW"),
        "BUD": ("BUX", "HUF"),
        "WAR": ("WSE", "PLN"),
        "PSE": ("PSE", "PHP"),
        "JK": ("JSX", "IDR"),
        "AU": ("ASX", "AUD"),
        "SHG": ("SEHK", "CNY"),
        "KAR": ("XKAR", "PKR"),
        "JSE": ("JSE", "ZAR"),
        "NSE": ("NSE", "INR"),
        "AT": ("ATH", "EUR"),
        "SHE": ("SZSE", "CNY"),
        "SN": ("SNSE", "CLP"),
        "BK": ("SET", "THB"),
        "CM": ("CSE", "LKR"),
        "VN": ("HOSE", "VND"),
        "KLSE": ("XKLS", "MYR"),
        "RO": ("BVB", "RON"),
        "SA": ("BOVESPA", "BRL"),
        "BA": ("MERVAL", "ARS"),
        "MX": ("MEXI", "MXN"),
        "IL": ("LSEETF", "USD"),
        "ZSE": ("ZSE", "EUR"),
        "TW": ("TSEC", "TWD"),
        "TWO": ("TPEX", "TWD"),
        "EUBOND": ("SMART", "EUR"),
        "LIM": ("BVL", "PEN"),
        "GBOND": ("SMART", "USD"),
        "MONEY": ("SMART", "USD"),
        "EUFUND": ("SMART", "EUR"),
        "IS": ("IBIS", "TRY"),
        "FOREX": ("IDEALPRO", "USD"),
        "CC": ("PAXOS", "USD")
    }

    def __init__(self, host, port, clientId, api_version):
        self.host = host
        self.port = port
        self.clientId = clientId
        self.api_version = api_version
        self.ib = IBApi()
        self.ib_thread = None
        self.next_req_id = 1
        self.market_calendars = {}

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

    def is_market_open(self, exchange):
        if exchange not in self.market_calendars:
            calendar_name = self.get_calendar_name(exchange)
            self.market_calendars[exchange] = xcals.get_calendar(calendar_name)

        now = pd.Timestamp.now(tz='UTC')
        return self.market_calendars[exchange].is_open_on_minute(now)

    def get_next_market_open(self, exchange):
        if exchange not in self.market_calendars:
            calendar_name = self.get_calendar_name(exchange)
            self.market_calendars[exchange] = xcals.get_calendar(calendar_name)

        now = pd.Timestamp.now(tz='UTC')
        next_open = self.market_calendars[exchange].next_open(now)
        return next_open.to_pydatetime()

    def get_calendar_name(self, exchange):
        calendar_mapping = {
            'US': 'XNYS',  # New York Stock Exchange
            'LSE': 'XLON',  # London Stock Exchange
            'F': 'XFRA',  # Frankfurt Stock Exchange
            'KO': 'XKRX',  # Korea Exchange
            'T': 'XTKS',  # Tokyo Stock Exchange
            'HK': 'XHKG',  # Hong Kong Stock Exchange
        }
        return calendar_mapping.get(exchange, 'XNYS')  # Default to NYSE if not found

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

    def get_market_price(self, isin, symbol, exchange, name):
        self.ensure_connection()
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

        # Try to get real-time data first
        try:
            return self.get_market_data_price(contract_details.contract)
        except Exception as e:
            logger.warning(f"Failed to get real-time data for {symbol}: {e}. Trying historical data...")

        # If real-time data fails, try historical data
        try:
            self.ib.event.clear()
            self.ib.reqHistoricalData(req_id, contract_details.contract, "", "1 D", "1 min", "TRADES", 1, 1, False, [])

            if not self.ib.event.wait(timeout=10):
                raise TimeoutError(f"Timeout waiting for historical data for {symbol}")

            if req_id not in self.ib.historical_data or not self.ib.historical_data[req_id]:
                raise ValueError(f"No historical data received for {symbol}")

            latest_bar = self.ib.historical_data[req_id][-1]
            return float(latest_bar.close)
        except Exception as e:
            logger.error(f"Failed to get historical data for {symbol}: {e}")
            raise

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
        try:
            self.ensure_connection()
            contract = self.create_contract(symbol, secType, exchange)

            order = Order()
            order.action = action
            order.orderType = "MKT"
            order.totalQuantity = quantity
            order.cashQty = 0  # Set this to 0 instead of None

            with self.ib.lock:
                if self.ib.nextorderId is None:
                    logger.error("nextorderId is None. Requesting new valid ID.")
                    self.ib.reqIds(-1)
                    if not self.ib.connected.wait(timeout=10):
                        raise TimeoutError("Timeout waiting for nextorderId")
                orderId = self.ib.nextorderId
                self.ib.nextorderId += 1

            logger.info(f"Placing order: Symbol={symbol}, Action={action}, Quantity={quantity}, OrderId={orderId}")
            self.ib.placeOrder(orderId, contract, order)
            logger.info(f"Order placed: {symbol} {action} {quantity}")
            return orderId
        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            return None

    def get_account_summary(self):
        self.ensure_connection()
        self.ib.account_summary = {}
        self.ib.reqAccountSummary(1, "All", "TotalCashValue,NetLiquidation")
        time.sleep(1)
        return self.ib.account_summary

    def get_positions(self):
        self.ensure_connection()
        self.ib.positions = {}
        self.ib.reqPositions()
        time.sleep(1)
        return self.ib.positions

    def cancel_all_orders(self):
        self.ensure_connection()
        self.ib.reqGlobalCancel()

    def get_server_time(self):
        self.ensure_connection()
        self.ib.event.clear()
        self.ib.reqCurrentTime()
        if not self.ib.event.wait(timeout=10):
            raise TimeoutError("Timeout waiting for server time")
        return self.ib.server_time