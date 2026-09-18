# Annapurna Stores Retail Analytics Platform

A complete, production-grade, local analytical data lakehouse and relational data warehouse running entirely from a single `docker compose up`.

## Quick Start (Cold Start Run)

To bring up the entire platform from cold start and run all tasks (A through F) with end-to-end verification:

```bash
docker compose up --build
```

To stop and remove containers and networks:
```bash
docker compose down
```

---

## System Architecture

The platform runs 3 containerized services:
1. **`postgres`** (`postgres:16` on port `5432`):
   - Stores operational master data (`stores`, `products`, `product_categories`, `price_revisions`).
   - Automatically initializes schema and data from `data/masters.sql` on startup.
2. **`minio`** (`quay.io/minio/minio:latest` on ports `9000` S3 API / `9001` Web Console):
   - Lakehouse object store hosting partitioned sales data in bucket `annapurna-lakehouse`.
3. **`analytics-platform`** (`python:3.11-slim` with DuckDB 1.1.3):
   - Automated ingestion, deduplication, Kimball dimensional modeling, SCD Type 2 point-in-time pricing, federated cross-system querying, and financial reconciliation.

---

## Tasks Summary & Proofs

- **Task A (Platform Setup & Data Landing)**:
  - Daily files are landed into MinIO S3 partitioned by `store_id` and `year_month` (`s3://annapurna-lakehouse/sales/store_id=<store_id>/year_month=<YYYY-MM>/`).
  - **Partition Pruning Evidence (Store S01 in October 2024)**:
    - Single Flat Folder: 4,457 files, 68,706,877 bytes (~65.52 MB).
    - Partitioned Layout: 31 files, 846,899 bytes (~827 KB).
    - **Reduction: 99.30% fewer files, 98.77% fewer bytes scanned!**

- **Task B (Idempotent Loading & Deduplication)**:
  - Grain: `(bill_no, line_no)` eliminates duplicate and partial re-sends.
  - 3 Consecutive Runs Proof:
    - Run 1: 1,120,924 rows | MD5: `59dbb49f776f507a69ecffa1f3394cbd`
    - Run 2: 1,120,924 rows | MD5: `59dbb49f776f507a69ecffa1f3394cbd`
    - Run 3: 1,120,924 rows | MD5: `59dbb49f776f507a69ecffa1f3394cbd`

- **Task C (Kimball Dimensional Model for Dashboard Slicing)**:
  - Star schema tables: `dim_store`, `dim_product`, `dim_category`, `dim_date`, and `fact_sales`.
  - Normalizes store names and addresses to prevent repetitive data on millions of lines.
  - Resolves June 2024 product code reissue using `(product_code, valid_from..valid_to)` -> `product_sk`.
  - Filters out `TAX` (GST) and `TENDER` (bill totals) to avoid doubling revenue.
  - Enables sub-second dashboard slicing across Store, Category, Day of Week, and Month.

- **Task D (March Prices Point-in-Time Query)**:
  - Parameterized SCD Type 2 query joining `price_revisions` where `reporting_date BETWEEN effective_from AND effective_to`.
  - Exactly identical query code run twice:
    - March 2024 (`2024-03-31`): Sunfeast Cookies 150g (`P100019`) = ₹62.95 (MRP ₹70.50).
    - October 2024 (`2024-10-31`): Sunfeast Cookies 150g (`P100019`) = ₹74.65 (MRP ₹83.61).

- **Task E (Federated Query Across S3 & PostgreSQL)**:
  - Single SQL query joining MinIO S3 parquet files directly with PostgreSQL master tables without copying.
  - `EXPLAIN ANALYZE` proof shows `POSTGRES_SCAN` on PostgreSQL, `PARQUET_SCAN` via HTTP range requests on MinIO, and `HASH_JOIN` in vectorized DuckDB memory.

- **Task F (Financial Reconciliation & Variance Root Cause Analysis)**:
  - 9 out of 12 months match with **₹0.00 variance**.
  - **March 2024 (-₹486,250.00)**: Revenue Scope Definition (institutional bulk order invoiced outside POS till).
  - **July 2024 (-₹232,131.70)**: Source Data Gap (Pune S07 3-day till outage; phoned-in figures).
  - **December 2024 (+₹50.48)**: Revenue Definition (bill-level rupee rounding vs exact line sum).
