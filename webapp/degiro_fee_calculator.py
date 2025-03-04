import gradio as gr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# Fee data structures
FEES = {
    "2023": {
        "stocks": {
            "Ireland": 2.00,
            "United States, Canada": 1.00,
            "Germany - Tradegate": 3.90,
            "Germany - XETRA & Major European Markets": 3.90,
            "Australia, Germany - Frankfurt, Hong Kong, Japan, Singapore": 5.00,
        },
        "etfs": {"ETF Core Selection": 0.00, "Worldwide": 2.00},
        "bonds": {"Belgium, France, Germany, Netherlands, Portugal": 2.00},
        "handling_fee": {"default": 1.00, "exceptions": ["Tradegate (Stocks)"]},
        "currency": {
            "Manual trade": {"fixed": 10.00, "percentage": 0.25},
            "Auto FX trader": {"fixed": 0.00, "percentage": 0.25},
        },
        "dividend_processing": {
            "fixed": 1.00,
            "percentage": 3.00,
            "max_percentage": 10.00,
        },
    },
    "2025": {
        "stocks": {
            "Ireland": 2.00,
            "United States, Canada": 1.00,
            "Germany - Tradegate": 3.90,
            "Germany - XETRA & Major European Markets": 3.90,
            "Australia, Germany - Frankfurt, Hong Kong, Japan, Singapore": 5.00,
        },
        "etfs": {"ETF Core Selection": 0.00, "Worldwide": 2.00},
        "bonds": {"Belgium, France, Germany, Netherlands, Portugal": 2.00},
        "leveraged_products": {
            "OTC (BNP Paribas, Société Générale)": 0.50,
            "Germany - Zertifikate-Börse Frankfurt": 2.00,
            "Euronext Access Paris": 2.00,
        },
        "options": {
            "Eurex (Germany)": 0.75,
            "MEFF (Spain)": 0.75,
            "Euronext (NL, BE, FR, PT)": 0.75,
            "Other Countries": 0.75,
            "US Options": 0.75,
        },
        "futures": {
            "Euronext": 0.75,
            "Eurex Indices": 0.75,
            "Eurex Other": 0.75,
            "IDEM": 0.75,
            "MEFF": 0.75,
            "OMX Sweden (Indices)": 0.75,
        },
        "handling_fee": {
            "default": 1.00,
            "exceptions": [
                "Tradegate (Stocks)",
                "BNP & SGC OTC Leveraged Products",
                "Options & Futures (excl. OMX Nordics)",
            ],
        },
        "currency": {
            "Manual trade": {"fixed": 10.00, "percentage": 0.25},
            "Auto FX trader": {"fixed": 0.00, "percentage": 0.25},
        },
        "dividend_processing": {
            "fixed": 0.00,
            "percentage": 0.00,
            "max_percentage": 0.00,
        },
    },
}


# Helper functions
def get_security_types(version):
    if version == "2023 (Custody)":
        return ["Stocks", "ETFs", "Bonds"]
    else:  # 2025 (Basic/Active/Trader)
        return ["Stocks", "ETFs", "Bonds", "Leveraged Products", "Options", "Futures"]


def get_exchanges(version, security_type):
    version_key = "2023" if version == "2023 (Custody)" else "2025"

    if security_type == "Stocks":
        return list(FEES[version_key]["stocks"].keys())
    elif security_type == "ETFs":
        return list(FEES[version_key]["etfs"].keys())
    elif security_type == "Bonds":
        return list(FEES[version_key]["bonds"].keys())
    elif security_type == "Leveraged Products" and version_key == "2025":
        return list(FEES[version_key]["leveraged_products"].keys())
    elif security_type == "Options" and version_key == "2025":
        return list(FEES[version_key]["options"].keys())
    elif security_type == "Futures" and version_key == "2025":
        return list(FEES[version_key]["futures"].keys())

    return []


def get_transaction_fee(version, security_type, exchange):
    version_key = "2023" if version == "2023 (Custody)" else "2025"

    if security_type == "Stocks":
        return FEES[version_key]["stocks"].get(exchange, 0)
    elif security_type == "ETFs":
        return FEES[version_key]["etfs"].get(exchange, 0)
    elif security_type == "Bonds":
        return FEES[version_key]["bonds"].get(exchange, 0)
    elif security_type == "Leveraged Products" and version_key == "2025":
        return FEES[version_key]["leveraged_products"].get(exchange, 0)
    elif security_type == "Options" and version_key == "2025":
        return FEES[version_key]["options"].get(exchange, 0)
    elif security_type == "Futures" and version_key == "2025":
        return FEES[version_key]["futures"].get(exchange, 0)

    return 0


def get_handling_fee(version, security_type, exchange):
    version_key = "2023" if version == "2023 (Custody)" else "2025"
    exceptions = FEES[version_key]["handling_fee"]["exceptions"]

    # Check if the exchange or security type is in the exceptions list
    for exception in exceptions:
        if exception in exchange or (
            version_key == "2025"
            and ("OTC" in exchange or security_type in ["Options", "Futures"])
        ):
            return 0

    return FEES[version_key]["handling_fee"]["default"]


def get_currency_fee(version, trade_value, method):
    version_key = "2023" if version == "2023 (Custody)" else "2025"
    currency_fees = FEES[version_key]["currency"]

    fixed = currency_fees[method]["fixed"]
    percentage = currency_fees[method]["percentage"]

    return fixed + (trade_value * percentage / 100)


def calculate_dividend_fee(version, dividend_amount):
    version_key = "2023" if version == "2023 (Custody)" else "2025"
    dividend_fee = FEES[version_key]["dividend_processing"]

    fixed = dividend_fee["fixed"]
    percentage_fee = dividend_amount * dividend_fee["percentage"] / 100
    max_fee = dividend_amount * dividend_fee["max_percentage"] / 100

    total_fee = fixed + percentage_fee
    if total_fee > max_fee:
        total_fee = max_fee

    return total_fee


# Main calculation function
def calculate_fees(
    version,
    security_type,
    exchange,
    trade_value,
    is_foreign_currency,
    currency_method=None,
    quantity=1,
    is_dividend=False,
    dividend_amount=0,
):
    results = {}

    # Transaction fee
    transaction_fee = get_transaction_fee(version, security_type, exchange)
    if security_type in ["Options", "Futures"]:
        transaction_fee *= quantity  # For options/futures, fee is per contract
    results["Transaction fee"] = transaction_fee

    # Handling fee
    handling_fee = get_handling_fee(version, security_type, exchange)
    results["Handling fee"] = handling_fee

    # Currency conversion fee if applicable
    currency_fee = 0
    if is_foreign_currency:
        currency_fee = get_currency_fee(version, trade_value, currency_method)
    results["Currency conversion fee"] = round(currency_fee, 2)

    # Dividend processing fee if applicable
    dividend_fee = 0
    if is_dividend:
        dividend_fee = calculate_dividend_fee(version, dividend_amount)
    results["Dividend processing fee"] = round(dividend_fee, 2)

    # Total fee
    total_fee = sum(results.values())
    results["Total fees"] = round(total_fee, 2)

    # Trade value
    results["Trade value"] = trade_value

    # Total cost (trade + fees)
    results["Total cost"] = trade_value + total_fee

    # Fee percentage
    results["Fee percentage"] = (
        round((total_fee / trade_value) * 100, 2) if trade_value > 0 else 0
    )

    return results


# Generate comparison data for different trade values
def generate_fee_comparison(
    version, security_type, exchange, is_foreign_currency, currency_method=None
):
    trade_values = [1000, 5000, 10000, 25000, 50000, 100000]
    comparison_data = []

    for value in trade_values:
        fees = calculate_fees(
            version,
            security_type,
            exchange,
            value,
            is_foreign_currency,
            currency_method if is_foreign_currency else None,
        )
        comparison_data.append(
            {
                "Trade Value": value,
                "Total Fees": fees["Total fees"],
                "Fee Percentage": fees["Fee percentage"],
            }
        )

    return pd.DataFrame(comparison_data)


# Create fee breakdown chart
def create_fee_breakdown_chart(fee_results):
    # Create data for pie chart
    labels = []
    values = []

    for key, value in fee_results.items():
        if (
            key not in ["Trade value", "Total cost", "Total fees", "Fee percentage"]
            and value > 0
        ):
            labels.append(key)
            values.append(value)

    if sum(values) == 0:
        return None

    fig = px.pie(
        names=labels,
        values=values,
        title="Fee Breakdown",
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(font=dict(size=14), margin=dict(t=50, b=0, l=0, r=0))

    return fig


# Create fee comparison chart
def create_fee_comparison_chart(comparison_df):
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=comparison_df["Trade Value"],
            y=comparison_df["Total Fees"],
            name="Total Fees (€)",
            marker_color="rgb(55, 83, 109)",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=comparison_df["Trade Value"],
            y=comparison_df["Fee Percentage"],
            name="Fee Percentage (%)",
            marker_color="rgb(26, 118, 255)",
            yaxis="y2",
        )
    )

    fig.update_layout(
        title="Fee Comparison for Different Trade Values",
        xaxis=dict(
            title="Trade Value (€)",
            tickmode="array",
            tickvals=comparison_df["Trade Value"],
            tickformat=",.0f",
        ),
        yaxis=dict(title="Total Fees (€)", side="left", showgrid=True),
        yaxis2=dict(
            title="Fee Percentage (%)", side="right", overlaying="y", showgrid=False
        ),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255, 255, 255, 0.5)"),
        hovermode="x unified",
    )

    return fig


# Process request and generate results
def process_trade(
    version,
    security_type,
    exchange,
    trade_value,
    is_foreign_currency,
    currency_method,
    quantity,
    is_dividend,
    dividend_amount,
    show_comparison,
):
    if not exchange or not security_type:
        return "Please select both security type and exchange.", None, None

    try:
        trade_value = float(trade_value)
        quantity = int(quantity) if quantity else 1
        dividend_amount = float(dividend_amount) if dividend_amount else 0
    except ValueError:
        return (
            "Please enter valid numeric values for trade value, quantity, and dividend amount.",
            None,
            None,
        )

    if trade_value <= 0:
        return "Trade value must be positive.", None, None

    # Calculate fees
    fee_results = calculate_fees(
        version,
        security_type,
        exchange,
        trade_value,
        is_foreign_currency,
        currency_method if is_foreign_currency else None,
        quantity,
        is_dividend,
        dividend_amount,
    )

    # Format output
    output = f"## Fee Breakdown for {version}\n\n"
    output += f"### Trade Details\n"
    output += f"- Security Type: {security_type}\n"
    output += f"- Exchange: {exchange}\n"
    output += f"- Trade Value: €{fee_results['Trade value']:,.2f}\n"

    if quantity > 1 and security_type in ["Options", "Futures"]:
        output += f"- Quantity: {quantity} contracts\n"

    if is_foreign_currency:
        output += f"- Foreign Currency: Yes (using {currency_method})\n"

    if is_dividend:
        output += f"- Dividend Amount: €{dividend_amount:,.2f}\n"

    output += f"\n### Fees\n"
    for key, value in fee_results.items():
        if (
            key not in ["Trade value", "Total cost", "Total fees", "Fee percentage"]
            and value > 0
        ):
            output += f"- {key}: €{value:,.2f}\n"

    output += f"\n### Totals\n"
    output += f"- Total Fees: €{fee_results['Total fees']:,.2f}\n"
    output += f"- Trade Cost (incl. fees): €{fee_results['Total cost']:,.2f}\n"
    output += f"- Fee Percentage: {fee_results['Fee percentage']:.2f}%\n"

    # Generate charts
    breakdown_chart = create_fee_breakdown_chart(fee_results)

    comparison_chart = None
    if show_comparison:
        comparison_df = generate_fee_comparison(
            version,
            security_type,
            exchange,
            is_foreign_currency,
            currency_method if is_foreign_currency else None,
        )
        comparison_chart = create_fee_comparison_chart(comparison_df)

    return output, breakdown_chart, comparison_chart


# Compare fees between 2023 and 2025
def compare_versions(
    security_type,
    exchange_2023,
    exchange_2025,
    trade_value,
    is_foreign_currency,
    currency_method,
):
    if not security_type or not exchange_2023 or not exchange_2025:
        return "Please select security type and exchanges for both versions."

    try:
        trade_value = float(trade_value)
    except ValueError:
        return "Trade value must be a number."

    if trade_value <= 0:
        return "Trade value must be positive."

    # Calculate fees for both versions
    fees_2023 = calculate_fees(
        "2023 (Custody)",
        security_type,
        exchange_2023,
        trade_value,
        is_foreign_currency,
        currency_method if is_foreign_currency else None,
    )

    fees_2025 = calculate_fees(
        "2025 (Basic/Active/Trader)",
        security_type,
        exchange_2025,
        trade_value,
        is_foreign_currency,
        currency_method if is_foreign_currency else None,
    )

    # Format comparison output
    output = f"## Fee Comparison: 2023 vs 2025\n\n"
    output += f"### Trade Details\n"
    output += f"- Security Type: {security_type}\n"
    output += f"- 2023 Exchange: {exchange_2023}\n"
    output += f"- 2025 Exchange: {exchange_2025}\n"
    output += f"- Trade Value: €{trade_value:,.2f}\n"

    if is_foreign_currency:
        output += f"- Foreign Currency: Yes (using {currency_method})\n"

    output += f"\n### 2023 (Custody) Fees\n"
    for key, value in fees_2023.items():
        if key not in ["Trade value", "Total cost", "Fee percentage"] and value > 0:
            output += f"- {key}: €{value:,.2f}\n"

    output += f"\n### 2025 (Basic/Active/Trader) Fees\n"
    for key, value in fees_2025.items():
        if key not in ["Trade value", "Total cost", "Fee percentage"] and value > 0:
            output += f"- {key}: €{value:,.2f}\n"

    output += f"\n### Comparison\n"
    diff = fees_2023["Total fees"] - fees_2025["Total fees"]
    diff_percentage = (
        (diff / fees_2023["Total fees"]) * 100 if fees_2023["Total fees"] > 0 else 0
    )

    output += f"- 2023 Total Fees: €{fees_2023['Total fees']:,.2f} ({fees_2023['Fee percentage']:.2f}%)\n"
    output += f"- 2025 Total Fees: €{fees_2025['Total fees']:,.2f} ({fees_2025['Fee percentage']:.2f}%)\n"

    if diff > 0:
        output += (
            f"- Savings with 2025: €{diff:,.2f} ({abs(diff_percentage):.2f}% lower)\n"
        )
    elif diff < 0:
        output += f"- Extra cost with 2025: €{abs(diff):,.2f} ({abs(diff_percentage):.2f}% higher)\n"
    else:
        output += "- No difference in fees between 2023 and 2025.\n"

    return output


# Interface update functions
def update_security_types(version):
    return gr.update(choices=get_security_types(version), value=None)


def update_exchanges(version, security_type):
    choices = get_exchanges(version, security_type)
    return gr.update(choices=choices, value=None if choices else None)


def update_exchanges_2023(security_type):
    choices = get_exchanges("2023 (Custody)", security_type)
    return gr.update(choices=choices, value=None if choices else None)


def update_exchanges_2025(security_type):
    choices = get_exchanges("2025 (Basic/Active/Trader)", security_type)
    return gr.update(choices=choices, value=None if choices else None)


def update_currency_methods(is_foreign_currency):
    return gr.update(visible=is_foreign_currency)


def update_dividend_amount(is_dividend):
    return gr.update(visible=is_dividend)


def update_quantity_visibility(security_type):
    return gr.update(visible=security_type in ["Options", "Futures"])


def toggle_advanced_options(show_advanced):
    return [gr.update(visible=show_advanced) for _ in range(3)]


# Create the Gradio interface
with gr.Blocks(title="DEGIRO Trade Fee Calculator", theme=gr.themes.Soft()) as app:
    gr.Markdown(
        """
        # DEGIRO Trade Fee Calculator
        
        This tool calculates trading fees for DEGIRO brokerage accounts based on the 2023 Custody and 2025 Basic/Active/Trader fee schedules.
        """
    )

    with gr.Tabs():
        with gr.TabItem("Fee Calculator"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Trade Parameters")

                    version = gr.Radio(
                        label="Fee Schedule",
                        choices=["2023 (Custody)", "2025 (Basic/Active/Trader)"],
                        value="2025 (Basic/Active/Trader)",
                    )

                    security_type = gr.Dropdown(
                        label="Security Type",
                        choices=get_security_types("2025 (Basic/Active/Trader)"),
                        value=None,
                    )

                    exchange = gr.Dropdown(label="Exchange", choices=[])

                    trade_value = gr.Number(
                        label="Trade Value (€)", value=1000, precision=2
                    )

                    quantity = gr.Number(
                        label="Quantity (for Options/Futures)",
                        value=1,
                        precision=0,
                        visible=False,
                    )

                    show_advanced = gr.Checkbox(
                        label="Show Advanced Options", value=False
                    )

                    with gr.Group(visible=False) as advanced_group1:
                        is_foreign_currency = gr.Checkbox(
                            label="Trade in Foreign Currency?"
                        )

                    with gr.Group(visible=False) as advanced_group2:
                        currency_method = gr.Radio(
                            label="Currency Conversion Method",
                            choices=["Manual trade", "Auto FX trader"],
                            value="Auto FX trader",
                            visible=False,
                        )

                    with gr.Group(visible=False) as advanced_group3:
                        is_dividend = gr.Checkbox(
                            label="Include Dividend Processing Fee?"
                        )

                        dividend_amount = gr.Number(
                            label="Dividend Amount (€)",
                            value=0,
                            precision=2,
                            visible=False,
                        )

                    show_comparison = gr.Checkbox(
                        label="Show Fee Comparison for Different Trade Values",
                        value=False,
                    )

                    calculate_button = gr.Button("Calculate Fees", variant="primary")

                with gr.Column(scale=2):
                    output = gr.Markdown()

                    with gr.Row():
                        with gr.Column():
                            breakdown_chart = gr.Plot(label="Fee Breakdown")

                        with gr.Column():
                            comparison_chart = gr.Plot(label="Fee Comparison")

        with gr.TabItem("Version Comparison"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Compare 2023 vs 2025 Fees")

                    comp_security_type = gr.Dropdown(
                        label="Security Type",
                        choices=["Stocks", "ETFs", "Bonds"],
                        value=None,
                    )

                    with gr.Row():
                        with gr.Column():
                            comp_exchange_2023 = gr.Dropdown(
                                label="2023 Exchange", choices=[]
                            )

                        with gr.Column():
                            comp_exchange_2025 = gr.Dropdown(
                                label="2025 Exchange", choices=[]
                            )

                    comp_trade_value = gr.Number(
                        label="Trade Value (€)", value=1000, precision=2
                    )

                    comp_is_foreign_currency = gr.Checkbox(
                        label="Trade in Foreign Currency?"
                    )

                    comp_currency_method = gr.Radio(
                        label="Currency Conversion Method",
                        choices=["Manual trade", "Auto FX trader"],
                        value="Auto FX trader",
                        visible=False,
                    )

                    compare_button = gr.Button("Compare Fees", variant="primary")

                with gr.Column():
                    comparison_output = gr.Markdown()

        with gr.TabItem("Help & Information"):
            gr.Markdown(
                """
                ## About DEGIRO Fee Structures
                
                DEGIRO offers different fee schedules based on account type:
                
                ### 2023 Custody
                The Custody account is designed for long-term investors who want their securities segregated. It typically has:
                - Higher dividend processing fees (€1.00 + 3.00% of dividend amount)
                - No shorting capabilities
                - No margin trading
                
                ### 2025 Basic/Active/Trader
                These account profiles allow for more advanced trading with:
                - No dividend processing fees
                - Options for shorting securities
                - Margin trading capabilities
                - Access to more advanced products (options, futures, leveraged products)
                
                ## Fee Components
                
                The calculator accounts for:
                
                1. **Transaction Fee**: Varies by security type and exchange
                2. **Handling Fee**: €1.00 per transaction (with exceptions)
                3. **Currency Conversion Fee**: For trading in non-euro markets
                   - Manual: €10.00 + 0.25% of trade value
                   - Auto FX: 0.25% of trade value
                4. **Dividend Processing Fee**: Only for Custody accounts
                
                ## Tips for Reducing Fees
                
                - Use Auto FX trader instead of manual currency conversion
                - Consider the ETF Core Selection for commission-free ETF trading
                - Larger trades are proportionally cheaper (% fee decreases)
                - For active traders, the 2025 schedules typically offer better rates
                
                ## Data Sources
                
                This calculator is based on the official DEGIRO fee schedules:
                - 2023 Custody Fee Schedule (November 1st, 2023)
                - 2025 Basic/Active/Trader Fee Schedule (January 1st, 2025)
                """
            )

    # Set up event handlers
    version.change(update_security_types, inputs=[version], outputs=[security_type])

    security_type.change(
        fn=lambda x, y: [update_exchanges(x, y), update_quantity_visibility(y)],
        inputs=[version, security_type],
        outputs=[exchange, quantity],
    )

    is_foreign_currency.change(
        update_currency_methods, inputs=[is_foreign_currency], outputs=[currency_method]
    )

    is_dividend.change(
        update_dividend_amount, inputs=[is_dividend], outputs=[dividend_amount]
    )

    show_advanced.change(
        toggle_advanced_options,
        inputs=[show_advanced],
        outputs=[advanced_group1, advanced_group2, advanced_group3],
    )

    calculate_button.click(
        process_trade,
        inputs=[
            version,
            security_type,
            exchange,
            trade_value,
            is_foreign_currency,
            currency_method,
            quantity,
            is_dividend,
            dividend_amount,
            show_comparison,
        ],
        outputs=[output, breakdown_chart, comparison_chart],
    )

    # Version comparison tab handlers
    comp_security_type.change(
        fn=lambda x: [update_exchanges_2023(x), update_exchanges_2025(x)],
        inputs=[comp_security_type],
        outputs=[comp_exchange_2023, comp_exchange_2025],
    )

    comp_is_foreign_currency.change(
        update_currency_methods,
        inputs=[comp_is_foreign_currency],
        outputs=[comp_currency_method],
    )

    compare_button.click(
        compare_versions,
        inputs=[
            comp_security_type,
            comp_exchange_2023,
            comp_exchange_2025,
            comp_trade_value,
            comp_is_foreign_currency,
            comp_currency_method,
        ],
        outputs=[comparison_output],
    )

if __name__ == "__main__":
    app.launch(share=True)  # Added share=True to create a public link
