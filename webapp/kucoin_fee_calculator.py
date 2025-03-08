import gradio as gr
import numpy as np
import decimal
from decimal import Decimal
import pandas as pd
import datetime
import json

# Set decimal precision
decimal.getcontext().prec = 28

# Initialize empty dataframe for trades
trades_df = pd.DataFrame(columns=[
    'Date', 'Action', 'BTC Amount', 'Price', 'USD Value', 
    'Fee', 'Total Paid/Retrieved', 'Notes'
])

def format_number(value, precision=8):
    """Format number with comma as decimal separator"""
    if isinstance(value, str):
        return value
    
    # Ensure we're working with a Decimal for maximum precision
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    
    formatted = f"{value:.{precision}f}"
    
    # Remove trailing zeros after decimal point
    if '.' in formatted:
        formatted = formatted.rstrip('0').rstrip('.')
    
    # Replace decimal point with comma
    formatted = formatted.replace('.', ',')
    
    return formatted

def calculate_market_buy(price, usd_amount, fee_rate, precision=8, exact_n=None):
    """Calculate Bitcoin transaction for market buy order"""
    # Use Decimal for maximum precision
    price = Decimal(str(price))
    usd_amount = Decimal(str(usd_amount))
    fee_rate = Decimal(str(fee_rate))
    
    # Calculate the theoretical BTC amount
    if exact_n is not None and exact_n.strip() != "":
        # Use the exact n value provided
        try:
            theoretical_btc = Decimal(exact_n.replace(',', '.'))
        except:
            # Fall back to calculated value if parsing fails
            theoretical_btc = usd_amount / price
    else:
        # Calculate theoretical BTC amount
        theoretical_btc = usd_amount / price
    
    # Round the BTC amount to get real amount
    factor = Decimal(str(10**precision))
    real_amount = Decimal(str(theoretical_btc * factor).split('.')[0]) / factor
    
    # Calculate actual value in USD based on real amount
    value_usd = real_amount * price
    
    # Calculate fee
    fee = value_usd * (fee_rate / Decimal('100'))
    
    # Calculate total paid
    total_paid = value_usd + fee
    
    return {
        "theoretical_n": format_number(theoretical_btc, 12),
        "real_n": format_number(real_amount, precision),
        "value_usd": format_number(value_usd, 6),
        "fee_paid": format_number(fee, 12),
        "total_paid": format_number(total_paid, 10),
        "raw_values": {
            "real_amount": real_amount,
            "price": price,
            "value_usd": value_usd,
            "fee": fee,
            "total_paid": total_paid
        }
    }

def calculate_market_sell(price, btc_amount, fee_rate, precision=8):
    """Calculate Bitcoin transaction for market sell order"""
    # Use Decimal for maximum precision
    price = Decimal(str(price))
    btc_amount = Decimal(str(btc_amount).replace(',', '.'))
    fee_rate = Decimal(str(fee_rate))
    
    # Calculate USD value (no rounding needed, we're selling exact BTC amount)
    value_usd = btc_amount * price
    
    # Calculate fee
    fee = value_usd * (fee_rate / Decimal('100'))
    
    # Calculate retrieved amount (USD received)
    retrieved_without_fees = value_usd
    retrieved = value_usd - fee
    
    return {
        "n": format_number(btc_amount, 10),
        "price": format_number(price, 2),
        "value_usd": format_number(value_usd, 10),
        "fee_exit": format_number(fee, 12),
        "retrieved_without_fees": format_number(retrieved_without_fees, 10),
        "retrieved": format_number(retrieved, 10),
        "raw_values": {
            "btc_amount": btc_amount,
            "price": price,
            "value_usd": value_usd,
            "fee": fee,
            "retrieved": retrieved
        }
    }

def add_trade_to_history(action, results, trade_notes=""):
    """Add trade to the history dataframe"""
    global trades_df
    
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if action == "Buy BTC":
        raw = results["raw_values"]
        new_trade = {
            'Date': date,
            'Action': 'Buy',
            'BTC Amount': float(raw["real_amount"]),
            'Price': float(raw["price"]),
            'USD Value': float(raw["value_usd"]),
            'Fee': float(raw["fee"]),
            'Total Paid/Retrieved': float(raw["total_paid"]),
            'Notes': trade_notes
        }
    else:  # Sell BTC
        raw = results["raw_values"]
        new_trade = {
            'Date': date,
            'Action': 'Sell',
            'BTC Amount': float(raw["btc_amount"]),
            'Price': float(raw["price"]),
            'USD Value': float(raw["value_usd"]),
            'Fee': float(raw["fee"]),
            'Total Paid/Retrieved': float(raw["retrieved"]),
            'Notes': trade_notes
        }
    
    trades_df = pd.concat([trades_df, pd.DataFrame([new_trade])], ignore_index=True)
    return trades_df

def format_trades_df_for_display(df):
    """Format the trades dataframe for display with comma decimal separator"""
    df_display = df.copy()
    
    # Format numeric columns with comma as decimal separator
    numeric_cols = ['BTC Amount', 'Price', 'USD Value', 'Fee', 'Total Paid/Retrieved']
    for col in numeric_cols:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(
                lambda x: format_number(x, 8 if col == 'BTC Amount' else 2)
            )
    
    return df_display

# Create the Gradio interface
with gr.Blocks(title="Bitcoin Trading Calculator with History") as app:
    gr.Markdown("# Bitcoin Trading Calculator with History")
    
    # Store current results for adding to history
    current_buy_results = gr.State(None)
    current_sell_results = gr.State(None)
    
    # Order type selection
    order_action = gr.Radio(
        label="Order Action",
        choices=["Buy BTC", "Sell BTC"],
        value="Buy BTC"
    )
    
    with gr.Row():
        # Left column for inputs
        with gr.Column(scale=1):
            # Buy inputs
            with gr.Group(visible=True) as buy_inputs:
                gr.Markdown("### Market Buy Order (Specify USD to spend)")
                buy_price = gr.Number(label="Bitcoin Buy Price (USD)", value=86963.9)
                usd_amount = gr.Number(label="USD Amount to Spend", value=1.0)
                
                exact_n_input = gr.Textbox(
                    label="Exact Theoretical BTC Amount (Optional)",
                    placeholder="Example: 0,00001149990243",
                    value="0,00001149990243",
                    info="Enter exact value to override calculation. Use comma as decimal separator."
                )
                
                buy_fee_rate = gr.Slider(
                    label="Fee Rate (%)", 
                    minimum=0.01, 
                    maximum=1.0, 
                    step=0.01, 
                    value=0.1,
                    info="Trading fee percentage"
                )
                
                buy_precision = gr.Slider(
                    label="Decimal Precision for BTC Rounding", 
                    minimum=1, 
                    maximum=12, 
                    step=1, 
                    value=8,
                    info="Number of decimal places to round BTC amount"
                )
            
            # Sell inputs
            with gr.Group(visible=False) as sell_inputs:
                gr.Markdown("### Market Sell Order (Specify BTC to sell)")
                sell_price = gr.Number(label="Bitcoin Sell Price (USD)", value=86678.7)
                btc_amount = gr.Textbox(
                    label="BTC Amount to Sell",
                    placeholder="Example: 0,0000114",
                    value="0,0000114",
                    info="Enter BTC amount to sell. Use comma as decimal separator."
                )
                
                sell_fee_rate = gr.Slider(
                    label="Fee Rate (%)", 
                    minimum=0.01, 
                    maximum=1.0, 
                    step=0.01, 
                    value=0.1,
                    info="Trading fee percentage"
                )
            
            calculate_button = gr.Button("Calculate", variant="primary")
            
            # Common trade note field
            trade_notes = gr.Textbox(
                label="Trade Notes (Optional)",
                placeholder="Add notes about this trade...",
                lines=2
            )
            
            # Button to add trade to history
            with gr.Row():
                add_trade_button = gr.Button("Add Trade to History", variant="secondary")
                clear_history_button = gr.Button("Clear Trade History", variant="stop")
        
        # Right column for outputs
        with gr.Column(scale=1):
            # Buy outputs
            with gr.Group(visible=True) as buy_outputs:
                gr.Markdown("### Buy Order Results")
                with gr.Group():
                    theoretical_output = gr.Textbox(
                        label="Theoretical BTC Amount (n)",
                        info="Full precision value before rounding"
                    )
                    real_n_output = gr.Textbox(
                        label="Actual BTC Amount (real_n)",
                        info="Rounded to specified precision"
                    )
                    buy_value_output = gr.Textbox(label="Value in USD")
                    buy_fee_output = gr.Textbox(label="Fee Paid")
                    buy_total_output = gr.Textbox(label="Total Paid (Value + Fee)")
                
                buy_json_output = gr.JSON(label="Buy Results as JSON", visible=False)
            
            # Sell outputs
            with gr.Group(visible=False) as sell_outputs:
                gr.Markdown("### Sell Order Results")
                with gr.Group():
                    sell_n_output = gr.Textbox(label="BTC Amount (n)")
                    sell_price_output = gr.Textbox(label="Sell Price (P_T)")
                    sell_fee_output = gr.Textbox(label="Fee Exit")
                    retrieved_wo_fees_output = gr.Textbox(label="Retrieved w/o Fees")
                    retrieved_output = gr.Textbox(label="Retrieved (Final USD)")
                
                sell_json_output = gr.JSON(label="Sell Results as JSON", visible=False)
    
    # Trade History Display
    with gr.Row():
        with gr.Column():
            gr.Markdown("## Trade History")
            trade_history = gr.Dataframe(
                label="Trade History",
                headers=["Date", "Action", "BTC Amount", "Price", "USD Value", "Fee", "Total Paid/Retrieved", "Notes"],
                datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
                col_count=(8, "fixed"),
                value=format_trades_df_for_display(trades_df)
            )
            # Add CSV download button
            csv_download = gr.Button("Download Trade History as CSV")
    
    # Toggle between buy and sell interfaces
    def toggle_interface(action):
        if action == "Buy BTC":
            return [
                gr.update(visible=True),  # buy_inputs
                gr.update(visible=False), # sell_inputs
                gr.update(visible=True),  # buy_outputs
                gr.update(visible=False)  # sell_outputs
            ]
        else:
            return [
                gr.update(visible=False), # buy_inputs
                gr.update(visible=True),  # sell_inputs
                gr.update(visible=False), # buy_outputs
                gr.update(visible=True)   # sell_outputs
            ]
    
    order_action.change(
        toggle_interface,
        inputs=[order_action],
        outputs=[buy_inputs, sell_inputs, buy_outputs, sell_outputs]
    )
    
    # Connect calculation functions
    def process_order(action, buy_price, usd_amount, exact_n, buy_fee_rate, buy_precision,
                      sell_price, btc_amount, sell_fee_rate):
        if action == "Buy BTC":
            results = calculate_market_buy(buy_price, usd_amount, buy_fee_rate, buy_precision, exact_n)
            return [
                results["theoretical_n"],
                results["real_n"],
                results["value_usd"],
                results["fee_paid"],
                results["total_paid"],
                results,
                None,  # Current sell results
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
            ]
        else:  # Sell BTC
            results = calculate_market_sell(sell_price, btc_amount, sell_fee_rate, 8)
            return [
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                None,  # Current buy results
                results,
                results["n"],
                results["price"],
                results["fee_exit"],
                results["retrieved_without_fees"],
                results["retrieved"],
                results
            ]
    
    def add_current_trade(action, buy_results, sell_results, notes):
        """Add the current calculation to the trade history"""
        global trades_df
        
        if action == "Buy BTC" and buy_results:
            trades_df = add_trade_to_history("Buy BTC", buy_results, notes)
        elif action == "Sell BTC" and sell_results:
            trades_df = add_trade_to_history("Sell BTC", sell_results, notes)
        
        return format_trades_df_for_display(trades_df)
    
    def clear_trade_history():
        """Clear the trade history dataframe"""
        global trades_df
        trades_df = pd.DataFrame(columns=[
            'Date', 'Action', 'BTC Amount', 'Price', 'USD Value', 
            'Fee', 'Total Paid/Retrieved', 'Notes'
        ])
        return format_trades_df_for_display(trades_df)
    
    def download_csv():
        """Download the trade history as CSV"""
        global trades_df
        csv_str = trades_df.to_csv(index=False)
        return csv_str
    
    # Connect event handlers
    calculate_button.click(
        process_order,
        inputs=[
            order_action, 
            buy_price, usd_amount, exact_n_input, buy_fee_rate, buy_precision,
            sell_price, btc_amount, sell_fee_rate
        ],
        outputs=[
            theoretical_output, real_n_output, buy_value_output, buy_fee_output, buy_total_output,
            current_buy_results, current_sell_results,
            sell_n_output, sell_price_output, sell_fee_output, retrieved_wo_fees_output, retrieved_output, sell_json_output
        ]
    )
    
    add_trade_button.click(
        add_current_trade,
        inputs=[order_action, current_buy_results, current_sell_results, trade_notes],
        outputs=[trade_history]
    )
    
    clear_history_button.click(
        clear_trade_history,
        inputs=[],
        outputs=[trade_history]
    )
    
    # Auto-trigger calculation on load
    calculate_button.click(fn=None)
    
    gr.Markdown("""
    ### Trade History
    - Click "Add Trade to History" to store the current calculation in the history table
    - Add optional notes to provide context for each trade
    - Download your trade history as a CSV file
    - Clear history if needed
    
    ### Market Order Formulas:
    
    **Market Buy (USD → BTC):**
    - Theoretical BTC Amount = USD Amount ÷ BTC Price
    - Actual BTC Amount = Floor(Theoretical Amount, precision)
    - Value in USD = Actual BTC Amount × BTC Price
    - Fee = Value in USD × Fee Rate
    - Total Paid = Value in USD + Fee
    
    **Market Sell (BTC → USD):**
    - Value in USD = BTC Amount × Sell Price
    - Fee Exit = Value in USD × Fee Rate
    - Retrieved Without Fees = Value in USD
    - Retrieved (Final USD) = Value in USD - Fee Exit
    """)

# Launch the app
app.launch()