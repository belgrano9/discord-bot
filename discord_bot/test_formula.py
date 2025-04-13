
executed_qty = 0.0012
executed_price = 83834
direction = -1

# Fees and Risk
m = 10  # You can adjust this or make it a parameter
f0 = 0.001  # Fee for market entry
ft = 0.001  # Fee for OCO exit
risk = 0.01 * m  # Risk amount
rr = 1.5  # Risk/reward ratio

# Calculate take profit and stop loss prices
tp = (risk * rr + executed_qty * executed_price * (f0 + direction)) / (executed_qty * (direction - ft))
sl = (risk - executed_qty * executed_price * (f0 + direction)) / (executed_qty * (ft - direction))

print(f"SL is {sl}")
print(f"TP is {tp}")