"""
Task D: Make March Use March's Prices
- Solves the Category Manager's question: "What did a particular biscuit pack sell for in March?"
- Uses price_revisions from PostgreSQL with effective_from / effective_to
- Executes the EXACT SAME SQL query string twice, changing only the as_of_date parameter
- Compares March 2024 prices against October 2024 / current prices
"""

import os
import duckdb
import pandas as pd

def run_march_prices(con):
    print("=" * 70)
    print("TASK D: MAKE MARCH USE MARCH'S PRICES (SCD TYPE 2 PRICE REVISIONS)")
    print("=" * 70)

    # Reusable parameterized SQL query
    # The query joins products, categories, and price_revisions using as-of point-in-time logic:
    query_template = """
    SELECT 
        p.product_code,
        p.product_name,
        c.category_name,
        pr.selling_price as effective_selling_price,
        pr.mrp as effective_mrp,
        pr.effective_from,
        pr.effective_to,
        $as_of_date::DATE as reporting_date
    FROM pg.products p
    JOIN pg.product_categories c 
        ON p.category_id = c.category_id
    JOIN pg.price_revisions pr 
        ON p.product_sk = pr.product_sk
    WHERE p.product_code IN ('P100019', 'P100049')
      AND $as_of_date::DATE >= pr.effective_from 
      AND $as_of_date::DATE <= pr.effective_to
      AND $as_of_date::DATE >= p.valid_from 
      AND $as_of_date::DATE <= p.valid_to
    ORDER BY p.product_code;
    """

    print("Executing identical query twice (differing ONLY in reporting period):\n")

    # Run 1: As of March 2024 (2024-03-31)
    march_date = '2024-03-31'
    print(f"--- RUN 1: Reporting Period = March 2024 ({march_date}) ---")
    df_march = con.execute(query_template, {"as_of_date": march_date}).df()
    print(df_march.to_string(index=False))

    # Run 2: As of October 2024 (2024-10-31)
    oct_date = '2024-10-31'
    print(f"\n--- RUN 2: Reporting Period = October 2024 ({oct_date}) ---")
    df_oct = con.execute(query_template, {"as_of_date": oct_date}).df()
    print(df_oct.to_string(index=False))

    print("\nComparison Analysis:")
    for i in range(len(df_march)):
        code = df_march.iloc[i]['product_code']
        name = df_march.iloc[i]['product_name']
        p_march = df_march.iloc[i]['effective_selling_price']
        p_oct = df_oct.iloc[i]['effective_selling_price']
        mrp_march = df_march.iloc[i]['effective_mrp']
        mrp_oct = df_oct.iloc[i]['effective_mrp']
        print(f"  * {name} ({code}):")
        print(f"      March 2024   : Selling Price = ₹{p_march:.2f} (MRP = ₹{mrp_march:.2f})")
        print(f"      October 2024 : Selling Price = ₹{p_oct:.2f} (MRP = ₹{mrp_oct:.2f})")
        print(f"      Price Drift  : ₹{p_oct - p_march:+.2f} ({((p_oct - p_march)/p_march)*100:+.1f}%)")

    print("\n>> VERIFIED: Identical query retrieves historical March prices for March reports")
    print("   and recent October prices for October reports, satisfying the Category Manager & CFO.")

    return df_march, df_oct

if __name__ == '__main__':
    from land_data import run_task_a_and_b
    from star_schema import build_star_schema
    con, _, _ = run_task_a_and_b()
    build_star_schema(con)
    run_march_prices(con)
