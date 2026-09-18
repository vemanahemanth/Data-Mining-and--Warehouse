"""
Task C: Kimball Star Schema Dimensional Modeling for Dashboard Slicing
- Prevents storing repetitive store address and metadata on millions of lines
- Resolves the June 2024 product code reissue using (product_code, valid_from..valid_to) -> product_sk
- Models special bill-level discounts (product_code = 'DISC') into a standardized discount dimension SKU
- Correctly filters non-revenue rows (TAX / GST, TENDER / bill totals) to prevent ~2x revenue inflation
- Builds dim_store, dim_product, dim_category, dim_date, and fact_sales
- Demonstrates rapid dashboard slicing across store, category, day of week, and month
"""

import os
import duckdb
import pandas as pd

def get_pg_conn_str():
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    port = os.environ.get('POSTGRES_PORT', '5432')
    db = os.environ.get('POSTGRES_DB', 'annapurna')
    user = os.environ.get('POSTGRES_USER', 'annapurna')
    pwd = os.environ.get('POSTGRES_PASSWORD', 'annapurna')
    return f"dbname={db} user={user} password={pwd} host={host} port={port}"

def build_star_schema(con):
    print("=" * 70)
    print("TASK C: DESIGN AND BUILD TABLES BEHIND THE DASHBOARD")
    print("=" * 70)

    # 1. Connect / attach PostgreSQL to DuckDB
    con.execute("INSTALL postgres; LOAD postgres;")
    pg_conn = get_pg_conn_str()
    print(f"[Task C] Attaching PostgreSQL operational database...")
    try:
        con.execute(f"ATTACH '{pg_conn}' AS pg (TYPE POSTGRES, READ_ONLY);")
    except Exception as e:
        if "already exists" not in str(e).lower():
            raise e

    # 2. Build Dimension Tables in Lakehouse / Analytical warehouse
    print("[Task C] Building Dimension Tables (dim_store, dim_product, dim_category, dim_date)...")
    
    # dim_store (Normalizes store name & address out of fact table)
    con.execute("""
    CREATE OR REPLACE TABLE dim_store AS
    SELECT 
        store_id,
        store_name,
        address_line,
        city,
        state,
        region,
        floor_area_sqft,
        opened_on
    FROM pg.stores;
    """)

    # dim_category (with standard entry for bill discounts)
    con.execute("""
    CREATE OR REPLACE TABLE dim_category AS
    SELECT 
        category_id,
        category_name,
        department,
        gst_rate
    FROM pg.product_categories;
    """)
    con.execute("""
    INSERT INTO dim_category VALUES ('C00', 'Bill Discounts', 'Discounts', 0.0);
    """)

    # dim_product (SCD Type 2 Dimension with product_sk, plus standard discount SKU 0)
    con.execute("""
    CREATE OR REPLACE TABLE dim_product AS
    SELECT 
        product_sk,
        product_code,
        product_name,
        category_id,
        brand,
        pack_size,
        uom,
        valid_from,
        valid_to,
        is_current
    FROM pg.products;
    """)
    con.execute("""
    INSERT INTO dim_product VALUES 
    (0, 'DISC', 'Bill Discount', 'C00', 'RetailEdge', '1', 'EA', DATE '2000-01-01', DATE '9999-12-31', TRUE);
    """)

    # dim_date (Calendar dimension for temporal slicing)
    con.execute("""
    CREATE OR REPLACE TABLE dim_date AS
    WITH date_series AS (
        SELECT unnest(generate_series(DATE '2024-01-01', DATE '2024-12-31', INTERVAL 1 DAY))::DATE as cal_date
    )
    SELECT 
        cal_date as date_key,
        strftime(cal_date, '%Y-%m-%d') as full_date,
        dayofweek(cal_date) as day_of_week_num,
        dayname(cal_date) as day_of_week_name,
        day(cal_date) as day_of_month,
        month(cal_date) as month_num,
        monthname(cal_date) as month_name,
        strftime(cal_date, '%Y-%m') as year_month,
        year(cal_date) as calendar_year,
        CASE WHEN dayofweek(cal_date) IN (0, 6) THEN TRUE ELSE FALSE END as is_weekend
    FROM date_series;
    """)

    # 3. Build Fact Table: fact_sales
    print("\n[Task C] Constructing fact_sales with business rules:")
    print("  1. Filter out TAX (GST) and TENDER (bill totals) -> prevents ~2x double-counting")
    print("  2. Join products on (product_code, valid_from <= date <= valid_to) to resolve surrogate key product_sk")
    print("  3. Map bill-level discounts (product_code = 'DISC') to product_sk = 0 (Bill Discounts)")
    print("  4. Compute net revenue contribution: qty * unit_price (negative for discounts/returns, cancelling for voids)")

    con.execute("""
    CREATE OR REPLACE TABLE fact_sales AS
    SELECT 
        s.bill_no,
        s.line_no,
        s.store_id,
        COALESCE(p.product_sk, 0) as product_sk,
        s.business_date as date_key,
        s.line_type,
        s.qty,
        s.unit_price,
        round(s.qty * s.unit_price, 2) as line_amount
    FROM lakehouse_sales s
    LEFT JOIN dim_product p
        ON s.product_code = p.product_code
        AND s.business_date >= p.valid_from
        AND s.business_date <= p.valid_to
    WHERE s.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID');
    """)

    fact_count = con.execute("SELECT count(*) FROM fact_sales").fetchone()[0]
    total_rev = con.execute("SELECT round(sum(line_amount), 2) FROM fact_sales").fetchone()[0]
    print(f"\n[Task C] fact_sales created: {fact_count:,} revenue rows, Total Net Revenue = ₹{total_rev:,.2f}")

    # 4. Demonstrate dashboard slicing across the 4 required dimensions
    print("\n" + "-" * 70)
    print("DASHBOARD SLICING DEMONSTRATIONS")
    print("-" * 70)

    # Slice 1: Revenue by Store
    print("\n1. Revenue Sliced by Store (Sample):")
    rev_by_store = con.execute("""
    SELECT 
        s.store_id,
        s.store_name,
        s.city,
        round(sum(f.line_amount), 2) as net_revenue,
        count(distinct f.bill_no) as total_bills
    FROM fact_sales f
    JOIN dim_store s ON f.store_id = s.store_id
    GROUP BY s.store_id, s.store_name, s.city
    ORDER BY net_revenue DESC
    LIMIT 5;
    """).df()
    print(rev_by_store.to_string(index=False))

    # Slice 2: Revenue by Product Category
    print("\n2. Revenue Sliced by Product Category (Sample):")
    rev_by_cat = con.execute("""
    SELECT 
        c.category_name,
        c.department,
        round(sum(f.line_amount), 2) as net_revenue,
        round(sum(f.qty), 0)::BIGINT as total_units_sold
    FROM fact_sales f
    JOIN dim_product p ON f.product_sk = p.product_sk
    JOIN dim_category c ON p.category_id = c.category_id
    GROUP BY c.category_name, c.department
    ORDER BY net_revenue DESC
    LIMIT 6;
    """).df()
    print(rev_by_cat.to_string(index=False))

    # Slice 3: Revenue by Day of the Week
    print("\n3. Revenue Sliced by Day of the Week:")
    rev_by_dow = con.execute("""
    SELECT 
        d.day_of_week_name,
        round(sum(f.line_amount), 2) as net_revenue,
        count(distinct f.bill_no) as total_bills
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.day_of_week_name, d.day_of_week_num
    ORDER BY d.day_of_week_num;
    """).df()
    print(rev_by_dow.to_string(index=False))

    # Slice 4: Revenue by Month
    print("\n4. Revenue Sliced by Month:")
    rev_by_month = con.execute("""
    SELECT 
        d.year_month,
        d.month_name,
        round(sum(f.line_amount), 2) as net_revenue
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year_month, d.month_name
    ORDER BY d.year_month;
    """).df()
    print(rev_by_month.to_string(index=False))

    return rev_by_store, rev_by_cat, rev_by_dow, rev_by_month

if __name__ == '__main__':
    from land_data import run_task_a_and_b
    con, _, _ = run_task_a_and_b()
    build_star_schema(con)
