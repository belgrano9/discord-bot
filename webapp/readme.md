# Trading Fee Calculators

A comprehensive suite of fee calculation tools for cryptocurrency and stock trading platforms, including Bitvavo and DEGIRO.

## Overview

This repository contains interactive web applications built to help users understand and calculate various fees associated with trading on different platforms:

1. **Bitvavo Fee Calculator** : Calculate cryptocurrency trading, deposit, and withdrawal fees on the Bitvavo exchange
2. **DEGIRO Trade Fee Calculator** : Calculate stock trading costs including transaction fees, handling fees, and currency conversion costs for DEGIRO brokerage accounts

Both calculators provide detailed breakdowns and visual representations of fee structures to help users make informed trading decisions.

## Features

### Bitvavo Fee Calculator

#### Trading Fee Calculator

* Calculate trading fees based on 30-day volume
* Support for different market categories (A, B, C, and USDC markets)
* Differentiation between maker and taker fees
* Visual fee structure charts
* Next tier information showing volume needed for better rates

#### Deposit Fee Calculator

* Calculate deposit fees for different payment methods
* Compare fees across all deposit methods
* Check maximum deposit limits
* Visual comparison of deposit fees by method

#### Withdrawal Fee Calculator

* Calculate cryptocurrency withdrawal fees
* Check minimum withdrawal amounts
* View fee as percentage of withdrawal amount
* Overview table of withdrawal fees for popular cryptocurrencies

#### Total Cost Calculator

* Combined calculation of trading and withdrawal fees
* Full breakdown of all costs involved in a complete transaction

### DEGIRO Trade Fee Calculator

* **Dual Fee Schedule Support** : Compare between 2023 Custody and 2025 Basic/Active/Trader fee structures
* **Comprehensive Fee Calculation** : Includes transaction fees, handling fees, currency conversion costs, dividend processing fees
* **Visual Fee Breakdown** : Pie charts showing fee composition
* **Fee Scaling Visualization** : Compare how fees scale with different trade values
* **Version Comparison Tool** : Directly compare costs between 2023 and 2025 fee structures
* **Advanced Options** : Configure currency conversion methods, dividend processing, and more
* **Verified Accuracy** : Tested against real DEGIRO fee statements

## Installation

### Requirements

* Python 3.7 or higher
* Required packages:
  * Bitvavo calculator: gradio, pandas, matplotlib, numpy
  * DEGIRO calculator: gradio, pandas, numpy, plotly

### Setup

```bash
# Clone the repository
git clone https://github.com/belgrano9/discord-bot.git
cd discord-bot/webapp

# Install required packages
pip install gradio pandas numpy matplotlib plotly
```

## Running the Applications

### Bitvavo Fee Calculator

```bash
python bitvavo_fee_calculator.py
```

### DEGIRO Trade Fee Calculator

```bash
python degiro_fee_calculator.py
```

After running either command, the application will start a local web server. Access the calculator through your web browser using the link provided in the terminal (typically http://127.0.0.1:7860).

For public access (valid for 72 hours), the applications create a sharable link when run with the `share=True` parameter.

## Usage Guide

### Bitvavo Fee Calculator

#### Trading Fees

1. Enter your 30-day trading volume
2. Enter the trade amount you want to calculate fees for
3. Select whether you are a maker or taker
   * Maker: when you place limit orders that don't execute immediately
   * Taker: when you place market orders or limit orders that execute immediately
4. Select the market category
5. Click "Calculate Fee"
6. View the fee structure visualization by selecting "Maker", "Taker", or "Both"

#### Deposit Fees

1. Enter the amount you want to deposit
2. Select the payment method
3. Click "Calculate Deposit Fee"
4. View the comparison chart showing fees across all methods

#### Withdrawal Fees

1. Enter the amount of cryptocurrency you want to withdraw
2. Select the cryptocurrency
3. Click "Calculate Withdrawal Fee"
4. Review the fee amount and percentage

#### Total Cost Calculator

1. Enter your trade amount, trading volume, and select market category
2. Enter cryptocurrency amount and type for withdrawal
3. Click "Calculate Total Cost"
4. View the complete breakdown of all fees

### DEGIRO Trade Fee Calculator

#### Basic Usage

1. Select the fee schedule version (2023 Custody or 2025 Basic/Active/Trader)
2. Choose a security type (Stocks, ETFs, Bonds, etc.)
3. Select the exchange/market
4. Enter the trade value in euros
5. Click "Calculate Fees"

#### Advanced Options

* **Foreign Currency** : Enable to simulate trades in non-EUR currencies
* **Currency Conversion Method** : Choose between Manual trade (€10.00 + 0.25%) or Auto FX trader (0.25%)
* **Dividend Processing** : Calculate additional fees for dividend payments (primarily for Custody accounts)
* **Fee Comparison** : View how fees scale with different trade values

#### Version Comparison

Use the "Version Comparison" tab to directly compare fees between 2023 and 2025 fee schedules for the same trade parameters.

## Understanding Fee Structures

### Bitvavo Fees

#### Trading Fees

Bitvavo uses a maker-taker fee model with tiered discounts based on 30-day trading volume:

* **Maker Fees** : Applied when adding liquidity (placing limit orders)
* **Taker Fees** : Applied when removing liquidity (placing market orders)
* **Fee Categories** :
* Category A: Most cryptocurrencies (BTC, ETH, etc.)
* Category B: Stablecoin pairs (USDC/EUR, EUROC/EUR, EUROP/EUR)
* Category C: Other euro pairs
* USDC markets: Special rates for USDC trading pairs

Both buying and selling can incur either maker or taker fees, depending on how the order is placed.

#### Deposit Fees

* SEPA transfers: 0% (Free)
* iDeal and Bancontact: 0% (Free)
* Credit card: 1.00%
* PayPal: 2.00%
* Other payment methods have varying fees

#### Withdrawal Fees

* Fixed fees that vary by cryptocurrency
* Each cryptocurrency has a minimum withdrawal amount
* Asset recovery fee: €50 for deposits sent on wrong networks

### DEGIRO Fees

#### Fee Components

* **Transaction Fee** : Base fee charged by DEGIRO for executing a trade, varies by security type and exchange
* **Handling Fee** : Fixed €1.00 fee per transaction (with exceptions)
* **Currency Conversion** : For trading in non-euro markets
* Manual: €10.00 + 0.25% of trade value
* Auto FX: 0.25% of trade value
* **Dividend Processing** : Fee charged when receiving dividends (primarily on Custody accounts)
* **Market Connectivity** : Annual/monthly fee for accessing certain exchanges

## Tips for Reducing Fees

### Bitvavo

* Higher trading volume results in lower fees
* Use maker orders when possible
* Withdraw larger amounts to minimize the impact of fixed fees

### DEGIRO

* Use Auto FX trader instead of manual currency conversion
* Consider the ETF Core Selection for commission-free ETF trading
* Larger trades are proportionally cheaper (% fee decreases)
* For active traders, the 2025 schedules typically offer better rates

## Code Structure

Both applications are organized into several key components:

1. **Data Structures** : Contains fee data for different categories and methods
2. **Calculator Functions** : Functions to calculate various fees
3. **Display Functions** : Format results for user-friendly display
4. **Visualization Functions** : Create charts and graphs
5. **Gradio Interface** : User interface components and event handlers

## Customization

You can customize these tools by:

1. Updating fee structures when platforms change their rates
2. Adding more assets/exchanges to the relevant sections
3. Modifying the UI styling by changing the color variables
4. Adding additional calculator functionalities

## Data Sources

* **Bitvavo** : Based on official Bitvavo fee schedules
* **DEGIRO** : Based on official DEGIRO fee schedules:
* 2023 Custody Fee Schedule (November 1st, 2023)
* 2025 Basic/Active/Trader Fee Schedule (January 1st, 2025)

## License

This project is provided for educational and informational purposes. Fee structures may change, and while every effort has been made to ensure accuracy, users should verify current fees on the official websites.

## Disclaimer

These calculators are not affiliated with, endorsed by, or connected to Bitvavo or DEGIRO/flatexDEGIRO Bank AG. All fee information is based on publicly available fee schedules and may change over time. Always check the official websites for the most current fee information.
