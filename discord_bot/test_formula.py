import numpy as np
executed_qty = 0.0012

executed_price = 84269.99
direction = -1

# Fees and Risk
m = 100  # You can adjust this or make it a parameter
f0 = 0.001  # Fee for market entry
ft = 0.001  # Fee for OCO exit
risk = 0.01  # Risk percentage
rr = 1.2  # Risk/reward ratio

# Calculate take profit and stop loss prices
tp = (risk * executed_price * rr + executed_price * (f0 + direction)) / (direction - ft)
sl = (risk * executed_price - executed_price * (f0 + direction)) / (ft - direction)

gained_value = direction * executed_qty * (tp - executed_price) - executed_qty * executed_price * f0 - executed_qty * tp * ft
lost_value = direction * executed_qty * (sl - executed_price) - executed_qty * executed_price * f0 - executed_qty * sl * ft
real_rr = np.round(- gained_value / lost_value, 3)
no_fees_rr = np.round((tp - executed_price) / (executed_price-sl), 3)
print(f"SL is {sl}")
print(f"TP is {tp}")
print(gained_value, lost_value)
print(real_rr == rr)
print(real_rr, no_fees_rr)