import duckdb

con = duckdb.connect()

# Load masters.sql into duckdb for testing
with open('data/masters.sql', 'r', encoding='utf-8') as f:
    sql = f.read()

# Filter out psql commands or run statements
# duckdb can execute standard SQL
statements = sql.split(';')
for s in statements:
    s = s.strip()
    if not s:
        continue
    # skip DROP TABLE ... CASCADE if unsupported, replace with simple DROP TABLE IF EXISTS
    s_clean = s.replace('CASCADE', '')
    try:
        con.execute(s_clean)
    except Exception as e:
        # print error if any
        pass

prod_cnt = con.execute("SELECT count(*) FROM products").fetchone()[0]
print(f"Loaded products: {prod_cnt}")

# Check reissued product codes
reissued = con.execute("""
SELECT product_code, count(*) 
FROM products 
GROUP BY product_code 
HAVING count(*) > 1
""").df()
print(f"Reissued product codes count: {len(reissued)}")
print(reissued.head())

# Check price_revisions
rev_cnt = con.execute("SELECT count(*) FROM price_revisions").fetchone()[0]
print(f"Loaded price revisions: {rev_cnt}")
