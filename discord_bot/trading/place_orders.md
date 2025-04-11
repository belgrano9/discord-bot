Okay, let's break down how to place **limit orders** using your `!realorder` command, covering the different buy/sell and borrowing scenarios.

Assuming you've fixed the parameter order in `cog.py` as discussed previously, the command structure relevant here is:

`!realorder <market> <side> <amount> <price> [auto_borrow]`

* `<market>`: e.g., `BTCUSDC`
* `<side>`: `buy` or `sell`
* `<amount>`: Quantity of the base asset (e.g., `0.001` BTC)
* `<price>`: **Crucially, for a limit order, this argument MUST be the price you want.** (e.g., `78000`)
* `[auto_borrow]`: Optional. `True` to enable borrowing, `False` or omitted to use existing funds/assets (defaults to `False`).

Here are the four main scenarios:

**1. Limit Buy (Standard - Using Existing Funds)**

* **Goal:** Buy BTC only if the price drops to $78,000, using your available USDC in the margin account.
* **Requirement:** You must have enough USDC in your Cross Margin account to cover the order value (`0.001 * 78000 = 78 USDC`).
* **`auto_borrow`:** `False` (or omitted). This tells the API to use `sideEffectType=NO_SIDE_EFFECT`.
* **Command:**

  ```
  !realorder BTCUSDC buy 0.001 78000
  ```

  or explicitly:
  ```
  !realorder BTCUSDC buy 0.001 78000 False
  ```

**2. Limit Sell (Standard - Selling Existing Assets)**

* **Goal:** Sell BTC you already own if the price rises to $80,000.
* **Requirement:** You must have at least `0.001` BTC available in your Cross Margin account.
* **`auto_borrow`:** `False` (or omitted). This tells the API to use `sideEffectType=NO_SIDE_EFFECT`.
* **Command:**

  ```
  !realorder BTCUSDC sell 0.001 80000
  ```

  or explicitly:
  ```
  !realorder BTCUSDC sell 0.001 80000 False
  ```

  * *If you try this without owning the BTC and without `auto_borrow=True`, you'll get the "Insufficient Balance" error.*

**3. Limit Buy (Margin Long - Borrowing Funds)**

* **Goal:** Buy BTC if the price drops to $78,000, *borrowing* the required USDC against your other collateral.
* **Requirement:** You need sufficient *collateral* (USDT, BUSD, other assets) in your Cross Margin account for Binance to allow you to borrow the `78 USDC`. Your available USDC balance doesn't matter as much as your overall margin health and collateral.
* **`auto_borrow`:** `True`. This tells the API to use `sideEffectType=AUTO_BORROW_REPAY` (which handles borrowing the quote currency on a buy).
* **Command:**
  ```
  !realorder BTCUSDC buy 0.001 78000 True
  ```

**4. Limit Sell (Margin Short - Borrowing Asset)**

* **Goal:** Open a short position by selling BTC if the price rises to $80,000 (or place a stop-entry sell), *borrowing* the BTC itself against your other collateral.
* **Requirement:** You need sufficient *collateral* (USDC, USDT, etc.) in your Cross Margin account for Binance to allow you to borrow `0.001` BTC.
* **`auto_borrow`:** `True`. This tells the API to use `sideEffectType=AUTO_BORROW_REPAY` (which handles borrowing the base currency on a sell).
* **Command:**
  ```
  !realorder BTCUSDC sell 0.001 80000 True
  ```

  * *This is the type of order that was failing for you with the market order previously due to the parameter order issue resulting in `NO_SIDE_EFFECT` being sent.*

**In Summary:**

* To place a **limit order**, always provide the desired `price` in the 4th position.
* To use **existing funds/assets**, set `auto_borrow` to `False` or omit it. Ensure you have the necessary balance (quote currency for buy, base currency for sell).
* To **borrow** (go long on margin or short on margin), set `auto_borrow` to `True`. Ensure you have sufficient *collateral* in your margin account.
