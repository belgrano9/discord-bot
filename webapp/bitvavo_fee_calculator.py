import gradio as gr
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Set theme colors to match Bitvavo's branding
BITVAVO_BLUE = "#0052FF"
BITVAVO_LIGHT_BLUE = "#E5EDFF"
BITVAVO_DARK = "#1E2026"
BITVAVO_GRAY = "#858585"

# Trading Fees Data
category_a_fees = {
    "volume_thresholds": [
        0,
        100000,
        250000,
        500000,
        1000000,
        2500000,
        5000000,
        10000000,
        25000000,
        100000000,
        500000000,
    ],
    "maker_fees": [0.15, 0.10, 0.08, 0.06, 0.05, 0.04, 0.04, 0.00, 0.00, 0.00, 0.00],
    "taker_fees": [0.25, 0.20, 0.16, 0.12, 0.10, 0.08, 0.06, 0.05, 0.02, 0.01, 0.01],
}

category_b_fees = {
    "volume_thresholds": [
        0,
        100000,
        250000,
        500000,
        1000000,
        2500000,
        5000000,
        10000000,
    ],
    "maker_fees": [0.10, 0.06, 0.04, 0.02, 0.01, 0.00, 0.00, 0.00],
    "taker_fees": [0.10, 0.06, 0.04, 0.02, 0.01, 0.01, 0.01, 0.01],
}

category_c_fees = {
    "volume_thresholds": [
        0,
        100000,
        250000,
        500000,
        1000000,
        2500000,
        5000000,
        10000000,
        25000000,
    ],
    "maker_fees": [0.15, 0.10, 0.08, 0.06, 0.05, 0.04, 0.04, 0.03, 0.03],
    "taker_fees": [0.25, 0.20, 0.16, 0.12, 0.10, 0.08, 0.06, 0.05, 0.04],
}

usdc_fees = {
    "volume_thresholds": [
        0,
        100000,
        250000,
        500000,
        1000000,
        2500000,
        5000000,
        10000000,
        25000000,
        100000000,
    ],
    "maker_fees": [0.05, 0.05, 0.05, 0.05, 0.05, 0.04, 0.04, 0.00, 0.00, 0.00],
    "taker_fees": [0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05, 0.02, 0.01],
}

# Deposit Fees
deposit_methods = {
    "SEPA Bank transfer": {
        "fixed_fee": 0.00,
        "percentage_fee": 0.00,
        "max_amount": 5000000,
    },
    "iDeal": {"fixed_fee": 0.00, "percentage_fee": 0.00, "max_amount": 50000},
    "Credit card": {"fixed_fee": 0.00, "percentage_fee": 0.01, "max_amount": 10000},
    "PayPal": {"fixed_fee": 0.00, "percentage_fee": 0.02, "max_amount": 10000},
    "Bancontact": {"fixed_fee": 0.00, "percentage_fee": 0.00, "max_amount": 10000},
    "EPS Überweisung": {
        "fixed_fee": 0.00,
        "percentage_fee": 0.0175,
        "max_amount": 1000,
    },
    "Giropay": {"fixed_fee": 0.00, "percentage_fee": 0.0175, "max_amount": 1000},
    "Sofort": {"fixed_fee": 0.00, "percentage_fee": 0.0225, "max_amount": 1000},
}

# Common withdrawal fees for popular cryptocurrencies
withdrawal_fees = {
    "Bitcoin (BTC)": {"fee": 0.0000053, "min_amount": 0.00001},
    "Ethereum (ETH)": {"fee": 0.000084, "min_amount": 0.000084},
    "Solana (SOL)": {"fee": 0.001, "min_amount": 0.001},
    "XRP": {"fee": 0, "min_amount": 10},
    "Cardano (ADA)": {"fee": 0.2, "min_amount": 2},
    "Polkadot (DOT)": {"fee": 0.08, "min_amount": 1},
    "Dogecoin (DOGE)": {"fee": 4, "min_amount": 4},
    "Litecoin (LTC)": {"fee": 0.001, "min_amount": 0.001},
    "USD Coin (USDC)": {"fee": 0.74, "min_amount": 0.74},
    "Euro Coin (EUROC)": {"fee": 0.7, "min_amount": 0.7},
}


def get_applicable_fee(volume, fee_type, category):
    """Get the applicable fee percentage based on volume and category"""
    if category == "Category A (Most cryptocurrencies)":
        fees = category_a_fees
    elif category == "Category B (Stablecoin pairs)":
        fees = category_b_fees
    elif category == "Category C (Other euro pairs)":
        fees = category_c_fees
    else:  # USDC markets
        fees = usdc_fees

    # Find the applicable fee tier based on volume
    applicable_fee = 0
    for i, threshold in enumerate(fees["volume_thresholds"]):
        if volume >= threshold:
            if fee_type == "Maker":
                applicable_fee = fees["maker_fees"][i]
            else:  # Taker
                applicable_fee = fees["taker_fees"][i]

    return applicable_fee


def calculate_trading_fee(volume, trade_amount, fee_type, category):
    """Calculate trading fee and return full results"""
    applicable_fee = get_applicable_fee(volume, fee_type, category)
    fee_amount = trade_amount * (applicable_fee / 100)
    next_tier = get_next_tier_info(volume, category)

    results = {
        "fee_percentage": applicable_fee,
        "fee_amount": fee_amount,
        "net_amount": trade_amount - fee_amount,
        "next_tier": next_tier,
    }

    return results


def get_next_tier_info(volume, category):
    """Get info about the next fee tier"""
    if category == "Category A (Most cryptocurrencies)":
        fees = category_a_fees
    elif category == "Category B (Stablecoin pairs)":
        fees = category_b_fees
    elif category == "Category C (Other euro pairs)":
        fees = category_c_fees
    else:  # USDC markets
        fees = usdc_fees

    next_threshold = None
    for threshold in fees["volume_thresholds"]:
        if threshold > volume:
            next_threshold = threshold
            break

    if next_threshold:
        volume_needed = next_threshold - volume
        return {"next_threshold": next_threshold, "volume_needed": volume_needed}
    else:
        return {"message": "You're already at the highest tier!"}


def display_trading_results(results, fee_type):
    """Format trading fee results for display"""
    fee_percentage = results["fee_percentage"]
    fee_amount = results["fee_amount"]
    net_amount = results["net_amount"]
    next_tier = results["next_tier"]

    html = f"""
    <div style="padding: 15px; border-radius: 10px; background-color: {BITVAVO_LIGHT_BLUE}; margin-bottom: 15px;">
        <h3 style="color: {BITVAVO_DARK}; margin-top: 0;">Fee Summary</h3>
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <div style="font-weight: bold;">{fee_type} Fee:</div>
            <div>{fee_percentage}%</div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <div style="font-weight: bold;">Fee Amount:</div>
            <div>€{fee_amount:.2f}</div>
        </div>
        <div style="display: flex; justify-content: space-between; padding-top: 10px; border-top: 1px solid #ccc;">
            <div style="font-weight: bold;">Net Amount:</div>
            <div>€{net_amount:.2f}</div>
        </div>
    </div>
    """

    if "next_threshold" in next_tier:
        html += f"""
        <div style="padding: 15px; border-radius: 10px; background-color: #f0f0f0;">
            <h3 style="color: {BITVAVO_DARK}; margin-top: 0;">Next Tier Information</h3>
            <p>Trade <strong>€{next_tier['volume_needed']:,.2f}</strong> more to reach the next tier at €{next_tier['next_threshold']:,}</p>
        </div>
        """
    else:
        html += f"""
        <div style="padding: 15px; border-radius: 10px; background-color: #f0f0f0;">
            <h3 style="color: {BITVAVO_DARK}; margin-top: 0;">Tier Status</h3>
            <p><strong>{next_tier['message']}</strong></p>
        </div>
        """

    return html


def create_fee_comparison_chart():
    """Create chart comparing fee structures across categories"""
    fig, ax = plt.subplots(figsize=(12, 7))

    # Set up data for comparison
    volumes = [0, 100000, 1000000, 10000000]
    volume_labels = ["€0", "€100K", "€1M", "€10M"]

    categories = [
        {"name": "Category A", "data": category_a_fees},
        {"name": "Category B", "data": category_b_fees},
        {"name": "Category C", "data": category_c_fees},
        {"name": "USDC", "data": usdc_fees},
    ]

    bar_width = 0.1
    positions = np.arange(len(volumes))

    # Plot taker fees for each category
    for i, category in enumerate(categories):
        taker_values = []
        for volume in volumes:
            fee = 0
            for j, threshold in enumerate(category["data"]["volume_thresholds"]):
                if volume >= threshold and j < len(category["data"]["taker_fees"]):
                    fee = category["data"]["taker_fees"][j]
            taker_values.append(fee)

        offset = bar_width * (i - 1.5)
        ax.bar(
            positions + offset,
            taker_values,
            bar_width,
            label=f"{category['name']} Taker",
            alpha=0.7,
            color=plt.cm.tab10(i),
        )

    ax.set_xticks(positions)
    ax.set_xticklabels(volume_labels)
    ax.set_ylabel("Fee Percentage (%)")
    ax.set_title("Taker Fee Comparison Across Categories")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    return fig


def create_fee_visualization(category, fee_type):
    """Create visualization of fee structure for a category"""
    if category == "Category A (Most cryptocurrencies)":
        fees = category_a_fees
    elif category == "Category B (Stablecoin pairs)":
        fees = category_b_fees
    elif category == "Category C (Other euro pairs)":
        fees = category_c_fees
    else:  # USDC markets
        fees = usdc_fees

    volumes = fees["volume_thresholds"]
    if fee_type == "Both":
        maker_fees = fees["maker_fees"]
        taker_fees = fees["taker_fees"]

        fig, ax = plt.subplots(figsize=(12, 6))

        ax.plot(
            volumes,
            maker_fees,
            "o-",
            label="Maker Fees",
            color=BITVAVO_BLUE,
            linewidth=2.5,
        )
        ax.plot(
            volumes,
            taker_fees,
            "o-",
            label="Taker Fees",
            color="#FF5733",
            linewidth=2.5,
        )

        # Fill the area between the curves
        ax.fill_between(volumes, maker_fees, taker_fees, color="lightgray", alpha=0.3)

    else:
        fig, ax = plt.subplots(figsize=(10, 6))
        if fee_type == "Maker":
            fee_data = fees["maker_fees"]
            color = BITVAVO_BLUE
        else:  # Taker
            fee_data = fees["taker_fees"]
            color = "#FF5733"

        ax.plot(volumes, fee_data, "o-", color=color, linewidth=3)
        ax.fill_between(volumes, fee_data, color=color, alpha=0.2)

    # Format x-axis with K and M for thousands and millions
    formatted_volumes = []
    for vol in volumes:
        if vol >= 1000000:
            formatted_volumes.append(f"€{vol/1000000:.0f}M")
        elif vol >= 1000:
            formatted_volumes.append(f"€{vol/1000:.0f}K")
        else:
            formatted_volumes.append(f"€{vol:.0f}")

    # Only show a subset of ticks if there are many
    if len(volumes) > 7:
        tick_indices = np.linspace(0, len(volumes) - 1, 6, dtype=int)
        tick_positions = [volumes[i] for i in tick_indices]
        tick_labels = [formatted_volumes[i] for i in tick_indices]
    else:
        tick_positions = volumes
        tick_labels = formatted_volumes

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)

    ax.set_xlabel("30-Day Trading Volume", fontsize=12)
    ax.set_ylabel("Fee Percentage (%)", fontsize=12)
    ax.set_title(f"{fee_type} Trading Fees: {category}", fontsize=14)

    # Add grid lines
    ax.grid(True, linestyle="--", alpha=0.7)

    if fee_type == "Both":
        ax.legend()

    plt.tight_layout()
    return fig


def calculate_deposit_fee(amount, method):
    """Calculate deposit fee and return detailed results"""
    if method not in deposit_methods:
        return {"error": "Method not available"}

    method_info = deposit_methods[method]

    if amount > method_info["max_amount"]:
        return {"error": f"Amount exceeds maximum of €{method_info['max_amount']:,}"}

    fee = method_info["fixed_fee"] + (amount * method_info["percentage_fee"])
    percentage = method_info["percentage_fee"] * 100

    return {
        "fee_amount": fee,
        "fee_percentage": percentage,
        "net_amount": amount - fee,
        "method": method,
        "max_amount": method_info["max_amount"],
    }


def display_deposit_results(results):
    """Format deposit fee results for display"""
    if "error" in results:
        return f"""
        <div style="padding: 15px; border-radius: 10px; background-color: #ffdddd;">
            <h3 style="color: #d32f2f; margin-top: 0;">Error</h3>
            <p>{results['error']}</p>
        </div>
        """

    fee_amount = results["fee_amount"]
    fee_percentage = results["fee_percentage"]
    net_amount = results["net_amount"]
    method = results["method"]
    max_amount = results["max_amount"]

    return f"""
    <div style="padding: 15px; border-radius: 10px; background-color: {BITVAVO_LIGHT_BLUE}; margin-bottom: 15px;">
        <h3 style="color: {BITVAVO_DARK}; margin-top: 0;">Deposit Summary - {method}</h3>
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <div style="font-weight: bold;">Fee Rate:</div>
            <div>{fee_percentage:.2f}%</div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <div style="font-weight: bold;">Fee Amount:</div>
            <div>€{fee_amount:.2f}</div>
        </div>
        <div style="display: flex; justify-content: space-between; padding-top: 10px; border-top: 1px solid #ccc;">
            <div style="font-weight: bold;">Net Deposit:</div>
            <div>€{net_amount:.2f}</div>
        </div>
    </div>
    <div style="padding: 15px; border-radius: 10px; background-color: #f0f0f0;">
        <p><strong>Maximum deposit amount:</strong> €{max_amount:,}</p>
    </div>
    """


def create_deposit_comparison_chart():
    """Create chart comparing deposit fees across methods"""
    methods = list(deposit_methods.keys())
    percentages = [deposit_methods[m]["percentage_fee"] * 100 for m in methods]

    # Sort methods by fee percentage
    sorted_indices = np.argsort(percentages)
    sorted_methods = [methods[i] for i in sorted_indices]
    sorted_percentages = [percentages[i] for i in sorted_indices]

    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.barh(sorted_methods, sorted_percentages, color=BITVAVO_BLUE, alpha=0.7)

    # Add value labels to the right of each bar
    for i, v in enumerate(sorted_percentages):
        if v > 0:
            ax.text(v + 0.05, i, f"{v:.2f}%", va="center")

    ax.set_xlabel("Fee Percentage (%)")
    ax.set_title("Deposit Fees by Payment Method")
    ax.set_xlim(0, max(percentages) * 1.2)  # Give some space for labels

    plt.tight_layout()
    return fig


def calculate_withdrawal_fee(crypto_amount, crypto_type):
    """Calculate cryptocurrency withdrawal fee"""
    if crypto_type not in withdrawal_fees:
        return {"error": "Cryptocurrency not found in the list"}

    fee_info = withdrawal_fees[crypto_type]
    fee_amount = fee_info["fee"]
    min_amount = fee_info["min_amount"]

    if crypto_amount < min_amount:
        return {
            "error": f"Amount below minimum withdrawal of {min_amount} {crypto_type.split(' ')[0]}"
        }

    net_amount = crypto_amount - fee_amount
    fee_percentage = (fee_amount / crypto_amount) * 100 if crypto_amount > 0 else 0

    return {
        "fee_amount": fee_amount,
        "fee_percentage": fee_percentage,
        "net_amount": net_amount,
        "crypto": crypto_type,
    }


def display_withdrawal_results(results):
    """Format withdrawal fee results for display"""
    if "error" in results:
        return f"""
        <div style="padding: 15px; border-radius: 10px; background-color: #ffdddd;">
            <h3 style="color: #d32f2f; margin-top: 0;">Error</h3>
            <p>{results['error']}</p>
        </div>
        """

    fee_amount = results["fee_amount"]
    fee_percentage = results["fee_percentage"]
    net_amount = results["net_amount"]
    crypto = results["crypto"]
    crypto_symbol = crypto.split(" ")[0] if "(" in crypto else crypto

    return f"""
    <div style="padding: 15px; border-radius: 10px; background-color: {BITVAVO_LIGHT_BLUE}; margin-bottom: 15px;">
        <h3 style="color: {BITVAVO_DARK}; margin-top: 0;">Withdrawal Summary - {crypto}</h3>
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <div style="font-weight: bold;">Fee Amount:</div>
            <div>{fee_amount} {crypto_symbol}</div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <div style="font-weight: bold;">Fee Percentage:</div>
            <div>{fee_percentage:.2f}%</div>
        </div>
        <div style="display: flex; justify-content: space-between; padding-top: 10px; border-top: 1px solid #ccc;">
            <div style="font-weight: bold;">Net Withdrawal:</div>
            <div>{net_amount} {crypto_symbol}</div>
        </div>
    </div>
    <div style="padding: 10px; border-radius: 5px; background-color: #fff3cd; margin-top: 10px;">
        <p><strong>Note:</strong> Withdrawal fees may vary due to blockchain network congestion.</p>
    </div>
    """


def calculate_total_cost(
    trade_amount, volume, trading_category, fee_type, crypto_amount, crypto_type
):
    """Calculate the total cost including trading and withdrawal fees"""
    # Calculate trading fee
    trading_results = calculate_trading_fee(
        volume, trade_amount, fee_type, trading_category
    )

    # Calculate withdrawal fee (we won't convert to EUR, just show separately)
    withdrawal_results = calculate_withdrawal_fee(crypto_amount, crypto_type)

    # If there's an error in withdrawal calculation, return only trading results
    if "error" in withdrawal_results:
        return {
            "trading_fee_amount": trading_results["fee_amount"],
            "trading_fee_percentage": trading_results["fee_percentage"],
            "withdrawal_fee": "N/A - Error in calculation",
            "withdrawal_fee_crypto": withdrawal_results.get("error", "Unknown error"),
            "net_amount_eur": trading_results["net_amount"],
            "total_fee_eur": trading_results["fee_amount"],
        }

    return {
        "trading_fee_amount": trading_results["fee_amount"],
        "trading_fee_percentage": trading_results["fee_percentage"],
        "withdrawal_fee": withdrawal_results["fee_amount"],
        "withdrawal_fee_percentage": withdrawal_results["fee_percentage"],
        "net_amount_eur": trading_results["net_amount"],
        "net_amount_crypto": withdrawal_results["net_amount"],
        "total_fee_eur": trading_results["fee_amount"],
        "crypto": crypto_type,
    }


def display_total_cost(results):
    """Format total cost results for display"""
    if "withdrawal_fee" == "N/A - Error in calculation":
        withdrawal_section = f"""
        <div style="padding: 10px; border-radius: 5px; background-color: #fff3cd; margin-top: 10px;">
            <p><strong>Note:</strong> {results["withdrawal_fee_crypto"]}</p>
        </div>
        """
    else:
        crypto_symbol = (
            results["crypto"].split(" ")[0]
            if "(" in results["crypto"]
            else results["crypto"]
        )
        withdrawal_section = f"""
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <div style="font-weight: bold;">Withdrawal Fee:</div>
            <div>{results["withdrawal_fee"]} {crypto_symbol} ({results["withdrawal_fee_percentage"]:.2f}%)</div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <div style="font-weight: bold;">Net Crypto Amount:</div>
            <div>{results["net_amount_crypto"]} {crypto_symbol}</div>
        </div>
        """

    return f"""
    <div style="padding: 15px; border-radius: 10px; background-color: {BITVAVO_LIGHT_BLUE}; margin-bottom: 15px;">
        <h3 style="color: {BITVAVO_DARK}; margin-top: 0;">Total Cost Summary</h3>
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <div style="font-weight: bold;">Trading Fee:</div>
            <div>€{results["trading_fee_amount"]:.2f} ({results["trading_fee_percentage"]}%)</div>
        </div>
        {withdrawal_section}
        <div style="display: flex; justify-content: space-between; padding-top: 10px; border-top: 1px solid #ccc;">
            <div style="font-weight: bold;">Net EUR Amount:</div>
            <div>€{results["net_amount_eur"]:.2f}</div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 10px;">
            <div style="font-weight: bold;">Total EUR Fees:</div>
            <div>€{results["total_fee_eur"]:.2f}</div>
        </div>
    </div>
    """


def initialize_plots(category, visualization_type):
    """Initialize the plots when the app starts"""
    return create_fee_visualization(category, visualization_type)


# Create Gradio Interface
with gr.Blocks(title="Bitvavo Fee Calculator", theme=gr.themes.Default()) as app:
    gr.Markdown(
        """
        # Bitvavo Fee Calculator
        
        <div style="display: flex; align-items: center; margin-bottom: 20px;">
            <div style="background-color: #0052FF; width: 4px; height: 24px; margin-right: 10px;"></div>
            <h2 style="margin: 0; color: #1E2026;">Understand all fees and costs when trading on Bitvavo</h2>
        </div>
        """
    )

    with gr.Tabs() as tabs:
        with gr.TabItem("Trading Fees"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Calculate your trading fees")

                    trading_volume = gr.Number(
                        label="30-day Trading Volume (€)",
                        value=1000,
                        info="Your trading volume from the past 30 days",
                    )

                    trade_amount = gr.Number(
                        label="Trade Amount (€)",
                        value=1000,
                        info="The amount you want to trade",
                    )

                    fee_type = gr.Radio(
                        ["Maker", "Taker"],
                        label="Fee Type",
                        info="Maker: adding liquidity (limit orders), Taker: removing liquidity (market orders)",
                        value="Taker",
                    )

                    category = gr.Dropdown(
                        [
                            "Category A (Most cryptocurrencies)",
                            "Category B (Stablecoin pairs)",
                            "Category C (Other euro pairs)",
                            "USDC markets",
                        ],
                        label="Market Category",
                        info="Different asset categories have different fee structures",
                        value="Category A (Most cryptocurrencies)",
                    )

                    calculate_button = gr.Button("Calculate Fee", variant="primary")

                with gr.Column(scale=1):
                    fee_result = gr.HTML(label="Fee Result")

            with gr.Row():
                with gr.Column():
                    visualization_type = gr.Radio(
                        ["Maker", "Taker", "Both"],
                        label="Fee Visualization",
                        value="Both",
                    )
                    fee_chart = gr.Plot(label="Fee Structure")

                with gr.Column():
                    gr.Markdown("### Fee Comparison Across Categories")
                    comparison_chart = gr.Plot(value=create_fee_comparison_chart())

        with gr.TabItem("Deposit Fees"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Calculate your deposit fees")

                    deposit_amount = gr.Number(
                        label="Deposit Amount (€)",
                        value=1000,
                        info="The amount you want to deposit",
                    )

                    payment_method = gr.Dropdown(
                        list(deposit_methods.keys()),
                        label="Payment Method",
                        info="Different payment methods have different fees",
                        value="SEPA Bank transfer",
                    )

                    deposit_button = gr.Button(
                        "Calculate Deposit Fee", variant="primary"
                    )

                with gr.Column(scale=1):
                    deposit_result = gr.HTML(label="Deposit Fee Result")

            with gr.Row():
                gr.Markdown("### Deposit Method Comparison")
                deposit_chart = gr.Plot(value=create_deposit_comparison_chart())

                method_info = pd.DataFrame(
                    [
                        {
                            "Method": method,
                            "Fixed Fee": f"€{info['fixed_fee']:.2f}",
                            "Percentage Fee": f"{info['percentage_fee']*100:.2f}%",
                            "Maximum Amount": f"€{info['max_amount']:,}",
                        }
                        for method, info in deposit_methods.items()
                    ]
                )
                deposit_info = gr.Dataframe(
                    value=method_info, label="Deposit Methods Overview"
                )

        with gr.TabItem("Withdrawal Fees"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Calculate cryptocurrency withdrawal fees")

                    crypto_amount = gr.Number(
                        label="Crypto Amount",
                        value=1,
                        info="The amount of cryptocurrency you want to withdraw",
                    )

                    crypto_type = gr.Dropdown(
                        list(withdrawal_fees.keys()),
                        label="Cryptocurrency",
                        info="Select the cryptocurrency you want to withdraw",
                        value="Bitcoin (BTC)",
                    )

                    withdrawal_button = gr.Button(
                        "Calculate Withdrawal Fee", variant="primary"
                    )

                with gr.Column(scale=1):
                    withdrawal_result = gr.HTML(label="Withdrawal Fee Result")

            with gr.Row():
                withdrawal_info = pd.DataFrame(
                    [
                        {
                            "Cryptocurrency": crypto,
                            "Fee Amount": f"{info['fee']} {crypto.split(' ')[0] if '(' in crypto else crypto}",
                            "Minimum Withdrawal": f"{info['min_amount']} {crypto.split(' ')[0] if '(' in crypto else crypto}",
                        }
                        for crypto, info in withdrawal_fees.items()
                    ]
                )
                gr.Dataframe(value=withdrawal_info, label="Withdrawal Fees Overview")

        with gr.TabItem("Total Cost Calculator"):
            gr.Markdown(
                "### Calculate total cost including trading and withdrawal fees"
            )

            with gr.Row():
                with gr.Column():
                    total_trade_amount = gr.Number(
                        label="Trade Amount (€)",
                        value=1000,
                        info="The amount you want to trade",
                    )

                    total_volume = gr.Number(
                        label="30-day Trading Volume (€)",
                        value=1000,
                        info="Your trading volume from the past 30 days",
                    )

                    total_category = gr.Dropdown(
                        [
                            "Category A (Most cryptocurrencies)",
                            "Category B (Stablecoin pairs)",
                            "Category C (Other euro pairs)",
                            "USDC markets",
                        ],
                        label="Market Category",
                        value="Category A (Most cryptocurrencies)",
                    )

                    total_fee_type = gr.Radio(
                        ["Maker", "Taker"], label="Fee Type", value="Taker"
                    )

                with gr.Column():
                    total_crypto_amount = gr.Number(
                        label="Crypto Amount to Withdraw",
                        value=1,
                        info="The amount of cryptocurrency you want to withdraw",
                    )

                    total_crypto_type = gr.Dropdown(
                        list(withdrawal_fees.keys()),
                        label="Cryptocurrency",
                        value="Bitcoin (BTC)",
                    )

                    total_button = gr.Button("Calculate Total Cost", variant="primary")

            with gr.Row():
                total_result = gr.HTML(label="Total Cost Result")

        with gr.TabItem("About"):
            gr.Markdown(
                """
                ## About Bitvavo Fees
                
                <div style="display: flex; align-items: flex-start; margin-bottom: 20px;">
                    <div style="background-color: #0052FF; width: 4px; min-height: 100%; margin-right: 15px;"></div>
                    <div>
                        <h3 style="margin-top: 0;">Trading Fees</h3>
                        <ul>
                            <li>Based on 30-day trading volume</li>
                            <li>Different rates for maker vs taker orders</li>
                            <li>Fees decrease with higher trading volumes</li>
                            <li>Category A: Most cryptocurrencies (BTC, ETH, SOL, etc.)</li>
                            <li>Category B: Stablecoin pairs (USDC/EUR, EUROC/EUR, EUROP/EUR)</li>
                            <li>Category C: All other euro pairs</li>
                            <li>USDC markets have their own fee structure</li>
                        </ul>
                    </div>
                </div>
                
                <div style="display: flex; align-items: flex-start; margin-bottom: 20px;">
                    <div style="background-color: #0052FF; width: 4px; min-height: 100%; margin-right: 15px;"></div>
                    <div>
                        <h3 style="margin-top: 0;">Deposit Fees</h3>
                        <ul>
                            <li>SEPA transfers are completely free</li>
                            <li>iDeal and Bancontact are also free</li>
                            <li>Credit card: 1.00% fee</li>
                            <li>PayPal: 2.00% fee</li>
                            <li>Other methods have varying fees</li>
                            <li>Each method has maximum deposit limits</li>
                        </ul>
                    </div>
                </div>
                
                <div style="display: flex; align-items: flex-start;">
                    <div style="background-color: #0052FF; width: 4px; min-height: 100%; margin-right: 15px;"></div>
                    <div>
                        <h3 style="margin-top: 0;">Withdrawal Fees</h3>
                        <ul>
                            <li>Fixed fees that vary by cryptocurrency</li>
                            <li>Fees may change due to blockchain network congestion</li>
                            <li>Each cryptocurrency has a minimum withdrawal amount</li>
                            <li>Asset recovery fee: €50 for deposits sent on wrong networks</li>
                        </ul>
                    </div>
                </div>
                
                <p style="margin-top: 30px; font-style: italic;">This app is for informational purposes only. Always check the <a href="https://bitvavo.com/en/fees" target="_blank">official Bitvavo website</a> for current fees.</p>
                """
            )

    # Event handlers
    calculate_button.click(
        fn=lambda vol, amt, type, cat: display_trading_results(
            calculate_trading_fee(vol, amt, type, cat), type
        ),
        inputs=[trading_volume, trade_amount, fee_type, category],
        outputs=[fee_result],
    )

    category.change(
        fn=create_fee_visualization,
        inputs=[category, visualization_type],
        outputs=[fee_chart],
    )

    visualization_type.change(
        fn=create_fee_visualization,
        inputs=[category, visualization_type],
        outputs=[fee_chart],
    )

    deposit_button.click(
        fn=lambda amt, method: display_deposit_results(
            calculate_deposit_fee(amt, method)
        ),
        inputs=[deposit_amount, payment_method],
        outputs=[deposit_result],
    )

    withdrawal_button.click(
        fn=lambda amt, type: display_withdrawal_results(
            calculate_withdrawal_fee(amt, type)
        ),
        inputs=[crypto_amount, crypto_type],
        outputs=[withdrawal_result],
    )

    total_button.click(
        fn=lambda amt, vol, cat, type, c_amt, c_type: display_total_cost(
            calculate_total_cost(amt, vol, cat, type, c_amt, c_type)
        ),
        inputs=[
            total_trade_amount,
            total_volume,
            total_category,
            total_fee_type,
            total_crypto_amount,
            total_crypto_type,
        ],
        outputs=[total_result],
    )

    # Initialize the fee chart when the app loads
    app.load(
        fn=initialize_plots, inputs=[category, visualization_type], outputs=[fee_chart]
    )

if __name__ == "__main__":
    app.launch()
