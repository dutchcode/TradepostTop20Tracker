# TradepostTop20Tracker

An open-source bot for InteractiveBrokers that tracks the Tradepost.ai Top20 Index.

## Description

This project implements an automated trading bot that mirrors the Tradepost.ai Top20 Index using an InteractiveBrokers account. It's designed for educational and demonstration purposes to showcase the practical application of the Tradepost.ai API.

## Prerequisites

1. An InteractiveBrokers account with API access enabled.
2. A Tradepost.ai account with API access. They offer a 14-day free trial which you can use to obtain an API key.
3. Python 3.9 or higher installed on your system.

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/dutchcode/TradepostTop20Tracker.git
   cd TradepostTop20Tracker
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Set up your InteractiveBrokers account and ensure you have API access enabled.

5. Sign up for a Tradepost.ai account and obtain your API key:
   - Go to [Tradepost.ai](https://tradepost.ai) and sign up for an account.
   - Once logged in, navigate to your account settings or API section to find your API key.
   - If you're using the 14-day free trial, make sure to note the expiration date.

6. Set up the configuration:
   - Copy the example configuration file:
     ```
     cp config.example.yaml config.yaml
     ```
   - Open `config.yaml` and fill in your actual values for the Tradepost API key, InteractiveBrokers account details, and other settings.

## Configuration

The `config.yaml` file contains all the necessary settings for the bot. Here's what you need to configure:

- `tradepost.api_key`: Your Tradepost.ai API key
- `interactive_brokers.account`: Your InteractiveBrokers account number
- `interactive_brokers.host`: Usually "127.0.0.1" for local connections
- `interactive_brokers.port`: 7497 for TWS paper trading, 4001 for IB Gateway paper trading
- `interactive_brokers.client_id`: A unique ID for this client connection
- `trading.rebalance_frequency`: How often to rebalance the portfolio
- `trading.cash_buffer`: Amount of cash to keep as a buffer for fees, etc.

Make sure to keep your `config.yaml` file secure and do not share it publicly, as it contains sensitive information.

## Usage

1. Make sure your InteractiveBrokers Trader Workstation (TWS) or IB Gateway is running and configured to accept API connections.

2. Activate your virtual environment if it's not already activated:
   ```
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Run the main script:
   ```
   python src/main.py
   ```

4. The bot will connect to InteractiveBrokers, fetch the latest Top20 data from Tradepost.ai, and execute trades to mirror the index.

## Development

To update all packages to their latest versions, you can use the following command:

```
pip list --outdated | cut -d ' ' -f 1 | xargs -n1 pip install -U
```

After updating packages, make sure to test the bot thoroughly as new versions might introduce breaking changes.

## Disclaimer

This is not financial advice. This bot is for educational and demonstration purposes only. Use at your own risk. Trading involves significant risk of loss and is not suitable for all investors. Make sure you understand the risks involved and the terms of service of both Tradepost.ai and InteractiveBrokers before using this bot.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgements

- [Tradepost.ai](https://tradepost.ai) for providing the Top20 Index API
- InteractiveBrokers for their trading API