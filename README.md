# TradepostTop20Tracker

An open-source bot for InteractiveBrokers that tracks the Tradepost.ai Top20 Index.

## ⚠️ WARNING: USE WITH CAUTION ⚠️

**IMPORTANT:** This bot will rebalance your portfolio to match the Tradepost.ai Top20 Index. It will sell stocks not in
the index and buy those that are.

- **DO NOT** connect this bot to an existing account with active positions unless you fully understand and accept the consequences.
- **ALWAYS** start with paper trading to familiarize yourself with the bot's behavior.
- Use a dedicated account for this bot to avoid unintended sales of other positions.

The authors and contributors of this project are not responsible for any financial losses incurred through the use of this bot. Use at your own risk.

## Description

This project implements an automated trading bot that mirrors the Tradepost.ai Top20 Index using an InteractiveBrokers account. It's designed for educational and demonstration purposes to showcase the practical application of the Tradepost.ai API.

## Key Features

- Daily rebalancing to match the Tradepost.ai Top20 Index
- Uses limit orders to avoid market impact
- Implements a "sell first, then buy" strategy to ensure cash availability
- Respects a maximum position size of 30% of the portfolio
- Maintains a configurable cash buffer

## Prerequisites

1. An InteractiveBrokers account with API access enabled.
2. Interactive Brokers Trader Workstation (TWS) or IB Gateway installed and running.
3. A Tradepost.ai account with API access. They offer a 14-day free trial which you can use to obtain an API key.
4. Python 3.9 or higher installed on your system.
5. Fractional shares trading enabled in your InteractiveBrokers account:
   - Visit the [Fractional Trading](https://www.interactivebrokers.com/en/trading/fractional-trading.php) page on the InteractiveBrokers website.
   - Follow the instructions to enable fractional shares trading for your account.
6. TWS/IB Gateway settings: 
   - [x] Enable ActiveX and Socket Clients
   - [ ] Read-Only API

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

## IBAPI Integration

This project includes the Interactive Brokers API (IBAPI) version 10.30.1 in the `vendor/ibapi` directory. This ensures compatibility and ease of setup across different environments.

If you need to update the IBAPI version:

1. Download the new version from the [Interactive Brokers website](https://interactivebrokers.github.io/).
2. Extract the `ibapi` folder from the downloaded package.
3. Replace the contents of `vendor/ibapi` with the new version.
4. Update this README to reflect the new version number.

Note: Always test thoroughly after updating the IBAPI version, as changes may affect the functionality of this project.

## Configuration

The `config.yaml` file contains all the necessary settings for the bot. Here's what you need to configure:

- `tradepost.api_key`: Your Tradepost.ai API key
- `interactive_brokers.account`: Your InteractiveBrokers account number
- `interactive_brokers.host`: Usually "127.0.0.1" for local connections
- `interactive_brokers.port`: 7497 for TWS paper trading, 4002 for IB Gateway paper trading
- `interactive_brokers.client_id`: A unique ID for this client connection
- `trading.cash_buffer`: Amount of cash to keep as a buffer for fees, etc.

Make sure to keep your `config.yaml` file secure and do not share it publicly, as it contains sensitive information.

## Usage

1. Ensure that either Interactive Brokers Trader Workstation (TWS) or IB Gateway is running and configured to accept API connections.

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
pip list --outdated --format=json | ConvertFrom-Json | ForEach-Object { pip install --upgrade $_.name }
```

After updating packages, make sure to test the bot thoroughly as new versions might introduce breaking changes.

## Disclaimer

This is not financial advice. This bot is for educational and demonstration purposes only. Use at your own risk. Trading involves significant risk of loss and is not suitable for all investors. Make sure you understand the risks involved and the terms of service of both Tradepost.ai and InteractiveBrokers before using this bot.

## License

This project is licensed under the GPL-3 License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgements

- [Tradepost.ai](https://tradepost.ai) for providing the Top20 Index API
- InteractiveBrokers for their trading API
