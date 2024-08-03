import time
from config import CONFIG
from tradepost_api import TradepostAPI

def main():
    tradepost = TradepostAPI(CONFIG['tradepost']['api_key'])

    while True:
        try:
            # Fetch the latest Top20 data
            top20_data = tradepost.get_top20()
            print(f"Fetched Top20 data for date: {top20_data['date']}")

            # TODO: Implement portfolio comparison and rebalancing logic

            # Sleep for a day (adjust as needed)
            time.sleep(86400)  # 24 hours

        except Exception as e:
            print(f"An error occurred: {e}")
            # Implement proper error handling and logging
            time.sleep(300)  # Wait 5 minutes before retrying

if __name__ == "__main__":
    main()