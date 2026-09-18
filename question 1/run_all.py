"""
Unified Master Runner for Annapurna Stores Retail Analytics Platform
Executes Tasks A through F end-to-end, validating cold-start reproducibility.
"""

import os
import sys
import time
import duckdb

from pipeline.wait_utils import wait_for_all_services
from pipeline.land_data import run_task_a_and_b
from pipeline.star_schema import build_star_schema
from pipeline.march_prices import run_march_prices
from pipeline.cross_system_query import run_cross_system_query
from pipeline.reconcile import run_reconciliation

def main():
    print("#" * 80)
    print("ANNAPURNA STORES RETAIL ANALYTICS PLATFORM - EXAM VERIFICATION SUITE")
    print("#" * 80)
    start_total = time.time()

    # Step 0: Ensure infrastructure is up and operational
    wait_for_all_services()

    # Step 1: Tasks A & B
    con, pruning, idempotency_results = run_task_a_and_b()

    # Step 2: Task C
    rev_by_store, rev_by_cat, rev_by_dow, rev_by_month = build_star_schema(con)

    # Step 3: Task D
    df_march, df_oct = run_march_prices(con)

    # Step 4: Task E
    df_fed, plan_text = run_cross_system_query(con)

    # Step 5: Task F
    recon_df, findings = run_reconciliation(con)

    total_time = time.time() - start_total
    print("\n" + "#" * 80)
    print(f"ALL TASKS (A THROUGH F) COMPLETED SUCCESSFULLY IN {total_time:.2f} SECONDS")
    print("#" * 80)

if __name__ == '__main__':
    main()
