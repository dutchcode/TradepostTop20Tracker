# TradepostTop20Tracker

An open-source bot for InteractiveBrokers that tracks the Tradepost.ai Top20 Index.

## Description

This project implements an automated trading bot that mirrors the Tradepost.ai Top20 Index using an InteractiveBrokers account. It's designed for educational and demonstration purposes to showcase the practical application of the Tradepost.ai API.

## Prerequisites

1. An InteractiveBrokers account with API access enabled.
2. A Tradepost.ai account with API access. They offer a 14-day free trial which you can use to obtain an API key.

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/dutchcode/TradepostTop20Tracker.git
   cd TradepostTop20Tracker
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Set up your InteractiveBrokers account and ensure you have API access enabled.

4. Sign up for a [Tradepost.ai](https://tradepost.ai) account and obtain your API key:
   
5. Update the `config.yaml` file with your Tradepost API key and InteractiveBrokers account details.

## Usage

1. Make sure your InteractiveBrokers Trader Workstation (TWS) or IB Gateway is running and configured to accept API connections.

2. Run the main script:
   ```
   python src/main.py
   ```

3. The bot will connect to InteractiveBrokers, fetch the latest Top20 data from Tradepost.ai, and execute trades to mirror the index.

## Configuration

In the `config.yaml` file:
- Set your Tradepost API key under `tradepost: api_key`
- Set your InteractiveBrokers details under the `interactive_brokers` section
- Adjust trading parameters as needed under the `trading` section

## Disclaimer

This is not financial advice. This bot is for educational and demonstration purposes only. Use at your own risk. Trading involves significant risk of loss and is not suitable for all investors. Make sure you understand the risks involved and the terms of service of both Tradepost.ai and InteractiveBrokers before using this bot.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [Tradepost.ai](https://tradepost.ai) for providing the Top20 Index API
- InteractiveBrokers for their trading API