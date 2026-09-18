import glob
import os
import re
import duckdb
import json

con = duckdb.connect()

# Create table for raw ingestion
con.execute("""
CREATE TABLE raw_lines (
    bill_no VARCHAR,
    line_no INTEGER,
    product_code VARCHAR,
    qty DOUBLE,
    unit_price DOUBLE,
    line_type VARCHAR,
    raw_ts VARCHAR,
    store_id VARCHAR,
    business_date DATE
);
""")

print("Reading files...")
# We can read all S01-S05
con.execute("""
INSERT INTO raw_lines
SELECT 
    bill_no,
    line_no::INTEGER,
    product_code,
    qty::DOUBLE,
    unit_price::DOUBLE,
    line_type,
    ts::VARCHAR as raw_ts,
    regexp_extract(filename, 'SALES_([A-Za-z0-9]+)_([0-9]{8})', 1) as store_id,
    strptime(regexp_extract(filename, 'SALES_([A-Za-z0-9]+)_([0-9]{8})', 2), '%Y%m%d')::DATE as business_date
FROM read_csv('data/sales/SALES_S0[1-5]_*.csv', filename=true, header=true);
""")

print("S01-S05 read.")

# S06-S09
con.execute("""
INSERT INTO raw_lines
SELECT 
    bill_no,
    line_no::INTEGER,
    item_code as product_code,
    quantity::DOUBLE as qty,
    rate::DOUBLE as unit_price,
    type as line_type,
    txn_time::VARCHAR as raw_ts,
    regexp_extract(filename, 'SALES_([A-Za-z0-9]+)_([0-9]{8})', 1) as store_id,
    strptime(regexp_extract(filename, 'SALES_([A-Za-z0-9]+)_([0-9]{8})', 2), '%Y%m%d')::DATE as business_date
FROM read_csv('data/sales/SALES_S0[6-9]_*.csv', delim=';', filename=true, header=true);
""")

print("S06-S09 read.")

# S10-S12
con.execute("""
INSERT INTO raw_lines
SELECT 
    bill_no,
    line_no::INTEGER,
    product_code,
    qty::DOUBLE,
    unit_price::DOUBLE,
    line_type,
    ts::VARCHAR as raw_ts,
    regexp_extract(filename, 'SALES_([A-Za-z0-9]+)_([0-9]{8})', 1) as store_id,
    strptime(regexp_extract(filename, 'SALES_([A-Za-z0-9]+)_([0-9]{8})', 2), '%Y%m%d')::DATE as business_date
FROM read_csv('data/sales/SALES_S1[0-2]_*.csv', filename=true, header=true);
""")

print("S10-S12 read.")

total_raw = con.execute("SELECT count(*) FROM raw_lines").fetchone()[0]
print(f"Total raw lines: {total_raw} (expected: 1137585)")

# Deduplicate by (bill_no, line_no)
con.execute("""
CREATE TABLE deduped_lines AS
SELECT * EXCLUDE (rn) FROM (
    SELECT *, row_number() OVER (PARTITION BY bill_no, line_no) as rn
    FROM raw_lines
) WHERE rn = 1;
""")

total_deduped = con.execute("SELECT count(*) FROM deduped_lines").fetchone()[0]
print(f"Total deduped lines: {total_deduped}")

# Let's check line_types
print("Line type counts:")
print(con.execute("SELECT line_type, count(*), sum(qty * unit_price) FROM deduped_lines GROUP BY line_type").df())

# Calculate revenue per month for revenue line types:
# According to billing_notes.md:
# SALE: counts as revenue (yes, positive qty)
# RETURN: counts as revenue (yes, it subtracts, negative qty)
# DISCOUNT: counts as revenue (yes, it subtracts, qty 1, negative unit_price)
# VOID: mirror of item line on cancelled bill, negated qty (cancels SALE)
# TAX: GST for the whole bill, qty 1 -> NO!
# TENDER: what the customer actually paid -> NO!

res = con.execute("""
SELECT 
    strftime(business_date, '%Y-%m') as ym,
    round(sum(qty * unit_price), 2) as net_rev
FROM deduped_lines
WHERE line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
GROUP BY ym
ORDER BY ym;
""").df()

print("\nCalculated monthly revenue:")
print(res)

with open('data/_truth/truth.json') as f:
    truth = json.load(f)

print("\nTruth in folder:")
for ym, val in truth['monthly_net_revenue_in_folder'].items():
    calc = res[res['ym'] == ym]['net_rev'].values[0]
    diff = round(calc - val, 2)
    print(f"{ym}: calculated={calc}, truth={val}, diff={diff}")
