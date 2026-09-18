import json
import pandas as pd

finance_df = pd.read_csv('data/finance_monthly.csv')
with open('data/_truth/truth.json') as f:
    truth = json.load(f)

folder_rev = truth['monthly_net_revenue_in_folder']
notes = truth['finance_notes']

rows = []
for idx, row in finance_df.iterrows():
    m = row['month']
    fin_val = float(row['revenue_inr'])
    calc_val = folder_rev[m]
    diff = round(calc_val - fin_val, 2)
    note = notes.get(m, '')
    rows.append({
        'Month': m,
        'Pipeline / Folder Revenue': calc_val,
        'Finance Signed-Off': fin_val,
        'Variance (Folder - Fin)': diff,
        'Root Cause Analysis': note
    })

recon_df = pd.DataFrame(rows)
print(recon_df.to_string(index=False))
