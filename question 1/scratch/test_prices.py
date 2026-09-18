import duckdb

con = duckdb.connect()

# Load schema and data
with open('data/masters.sql', 'r', encoding='utf-8') as f:
    sql = f.read()
for s in sql.split(';'):
    s = s.strip()
    if not s: continue
    try: con.execute(s.replace('CASCADE', ''))
    except: pass

# Let's inspect products in category C01 (Biscuits & Snacks)
biscuit = con.execute("""
SELECT p.product_sk, p.product_code, p.product_name, pr.selling_price, pr.effective_from, pr.effective_to
FROM products p
JOIN price_revisions pr ON p.product_sk = pr.product_sk
WHERE p.category_id = 'C01'
ORDER BY p.product_sk, pr.effective_from
LIMIT 20;
""").df()
print("Sample biscuit price revisions:")
print(biscuit)

# Query template: Given a reporting date or period (e.g. :as_of_date or :period_start), what was the selling price?
# For example, for March 2024 (e.g. DATE '2024-03-15' or DATE '2024-03-31') vs October 2024 (DATE '2024-10-15')
sample_sk = biscuit['product_sk'].iloc[0]
print(f"\nChecking product_sk {sample_sk} history:")
print(con.execute(f"SELECT * FROM price_revisions WHERE product_sk = {sample_sk} ORDER BY effective_from").df())
