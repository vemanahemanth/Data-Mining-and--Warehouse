# Walkthrough: Annapurna Stores Retail Analytics Platform

Platform implementation and experimental verification for **Question 1: Three Answers to One Question** (Tasks A through F).

---

## Architecture Overview

```
                                  +---------------------------------------+
                                  |         Single Docker Compose         |
                                  +---------------------------------------+
                                                      |
                 +------------------------------------+------------------------------------+
                 |                                    |                                    |
                 v                                    v                                    v
      +---------------------+              +---------------------+              +---------------------+
      |     PostgreSQL      |              |    MinIO (S3 API)   |              |   DuckDB Engine /   |
      |   Operational DB    |              |   Lakehouse Storage |              |   Pipeline Service  |
      +---------------------+              +---------------------+              +---------------------+
      | - stores            |              | Bucket:             |              | - Ingestion engine  |
      | - products (SCD-2)  |              |   annapurna-lakehouse|             | - Deduplication     |
      | - product_categories|              | Layout:             |              | - Star schema / DWH |
      | - price_revisions   |              |   sales/store_id=...|              | - Cross-system join |
      | Port: 5432          |              |   /year_month=.../  |              | - Automated report  |
      | Loaded: masters.sql |              | Ports: 9000, 9001   |              |   & verification    |
      +---------------------+              +---------------------+              +---------------------+
                 ^                                    ^                                    |
                 |                                    |                                    |
                 +----------------- Federated Query --+------------------------------------+
                                 (No copying between stores)
```

The platform runs from cold start via:
```bash
docker compose up --build
```

---

## Detailed Task Results & Verifications

### Task A: Stand the Platform Up and Land the Data

- **Object Store**: MinIO S3 API on port 9000 (Console on 9001), bucket `annapurna-lakehouse`.
- **Relational Database**: PostgreSQL 16 on port 5432, loaded with operational master tables from [`data/masters.sql`](file:///c:/Users/ub02-glab-025/Desktop/lab_exam/data/masters.sql).
- **Analytical Query Engine**: Vectorized DuckDB engine with `httpfs` and `postgres` extensions.
- **Partitioning Strategy**: Hive-style partition layout organized by `store_id` and `year_month`:
  ```
  s3://annapurna-lakehouse/sales/store_id=<store_id>/year_month=<YYYY-MM>/
  ```

#### Partition Pruning Proof: Store S01 in October 2024
To satisfy a query targeting Store `S01` in October 2024 (`2024-10`):

| Layout Organization | Files Scanned | Bytes Scanned | Reduction |
| :--- | :--- | :--- | :--- |
| **Single Flat Folder** | 4,457 files | 68,706,877 bytes (65.52 MB) | Baseline (100%) |
| **Partitioned Layout** | **31 files** | **846,899 bytes (827.05 KB)** | **99.30% fewer files, 98.77% fewer bytes!** |

---

### Task B: Make It Safe to Run Twice (Idempotency Proof)

- **Root Cause of Duplication**: Till servers periodically re-send exports with `__R1` and `__R2` suffixes. While most re-sends are byte-identical replacements, some are partial rollouts (e.g. November mid-roll issues).
- **Safe Grain**: Deduplicating on line level `(bill_no, line_no)` guarantees exact deduplication regardless of file fragmentation.
- **Total Raw Lines Ingested**: 1,137,585 across 4,457 files.
- **Unique Deduplicated Lines**: 1,120,924 lines.

#### Idempotency Verification (3 Consecutive Execution Runs)
| Run | Row Count | MD5 Checksum of Data State | Execution Time |
| :--- | :--- | :--- | :--- |
| **Run 1** | 1,120,924 | `59dbb49f776f507a69ecffa1f3394cbd` | 0.91s |
| **Run 2** | 1,120,924 | `59dbb49f776f507a69ecffa1f3394cbd` | 0.91s |
| **Run 3** | 1,120,924 | `59dbb49f776f507a69ecffa1f3394cbd` | 0.90s |

> [!NOTE]
> All 3 runs yield identical row counts (1,120,924) and identical cryptographic MD5 checksums, proving idempotency.

---

### Task C: Design the Tables Behind the Dashboard

Implemented a Kimball Star Schema to eliminate repeating store addresses and metadata across millions of sales records while resolving catalog anomalies:

1. **Dimensional Tables**:
   - `dim_store`: Normalizes store name, address, city, state, region, floor area.
   - `dim_category`: Normalizes product categories, departments, and GST rates.
   - `dim_product`: SCD Type 2 product dimension with surrogate key `product_sk`.
   - `dim_date`: Calendar dimension enabling temporal slicing by day of week, month, and weekend status.
2. **Crucial Source Data Nuances Handled**:
   - **Nuance 1 (Non-sale Lines & The 2x Revenue Warning)**:
     - Filtered out `TAX` (GST) and `TENDER` (bill total).
     - As noted in the warning, including `TENDER` roughly doubles total revenue because `TENDER` is the bill total written as a separate row in the same export!
   - **Nuance 2 (Reissued Product Codes)**:
     - In June 2024, 24 product codes were reissued to different products.
     - Resolved by joining on `raw.product_code = p.product_code AND raw.business_date BETWEEN p.valid_from AND p.valid_to` to assign `product_sk`.
   - **Nuance 3 (Bill-Level Discounts)**:
     - Bill discounts (`line_type = 'DISCOUNT'`, code `DISC`) are mapped to surrogate SKU `0` (`Bill Discounts`) so net discounts subtract properly without dropping rows.

#### Rapid Dashboard Slicing Demonstrations

##### 1. Revenue Sliced by Store (Sample)
| Store ID | Store Name | City | Net Revenue (INR) | Total Bills |
| :--- | :--- | :--- | :--- | :--- |
| **S03** | Annapurna T Nagar | Chennai | ₹62,502,249.41 | 19,695 |
| **S10** | Annapurna Rajouri Garden | New Delhi | ₹59,907,824.20 | 18,910 |
| **S01** | Annapurna Jayanagar | Bengaluru | ₹57,570,277.26 | 18,041 |
| **S06** | Annapurna Andheri West | Mumbai | ₹53,113,330.16 | 16,708 |
| **S02** | Annapurna Koramangala | Bengaluru | ₹47,671,324.31 | 14,790 |

##### 2. Revenue Sliced by Product Category (Sample)
| Category Name | Department | Net Revenue (INR) | Total Units Sold |
| :--- | :--- | :--- | :--- |
| **Staples & Grains** | Food | ₹98,677,244.71 | 119,614 |
| **Baby Care** | Non-Food | ₹88,746,237.02 | 113,442 |
| **Edible Oils** | Food | ₹82,736,636.78 | 111,533 |
| **Dairy** | Fresh | ₹39,696,588.61 | 121,431 |
| **Personal Care** | Non-Food | ₹37,437,446.74 | 92,597 |

##### 3. Revenue Sliced by Day of the Week
| Day of Week | Net Revenue (INR) | Total Bills |
| :--- | :--- | :--- |
| **Sunday** | ₹95,912,812.79 | 30,049 |
| **Monday** | ₹60,181,610.00 | 18,821 |
| **Tuesday** | ₹59,121,274.76 | 18,429 |
| **Wednesday** | ₹61,402,756.72 | 19,342 |
| **Thursday** | ₹65,680,681.53 | 20,554 |
| **Friday** | ₹79,837,449.80 | 25,190 |
| **Saturday** | ₹105,999,366.53 | 33,319 |

##### 4. Revenue Sliced by Month
| Month | Month Name | Net Revenue (INR) |
| :--- | :--- | :--- |
| **2024-01** | January | ₹38,446,071.33 |
| **2024-02** | February | ₹34,887,085.55 |
| **2024-03** | March | ₹41,971,649.09 |
| **2024-04** | April | ₹37,958,457.37 |
| **2024-05** | May | ₹41,764,716.40 |
| **2024-06** | June | ₹38,987,082.82 |
| **2024-07** | July | ₹40,295,160.11 |
| **2024-08** | August | ₹45,252,181.75 |
| **2024-09** | September | ₹44,615,037.46 |
| **2024-10** | October | ₹56,359,195.92 |
| **2024-11** | November | ₹51,583,838.47 |
| **2024-12** | December | ₹50,745,259.48 |

---

### Task D: Make March Use March's Prices

Executed the parameterized SCD Type 2 query twice without changing SQL code, differing only in the reporting date parameter (`2024-03-31` vs `2024-10-31`):

```sql
SELECT 
    p.product_code,
    p.product_name,
    c.category_name,
    pr.selling_price AS effective_selling_price,
    pr.mrp AS effective_mrp,
    pr.effective_from,
    pr.effective_to,
    $as_of_date::DATE AS reporting_date
FROM pg.products p
JOIN pg.product_categories c ON p.category_id = c.category_id
JOIN pg.price_revisions pr ON p.product_sk = pr.product_sk
WHERE p.product_code IN ('P100019', 'P100049')
  AND $as_of_date::DATE >= pr.effective_from 
  AND $as_of_date::DATE <= pr.effective_to
  AND $as_of_date::DATE >= p.valid_from 
  AND $as_of_date::DATE <= p.valid_to
ORDER BY p.product_code;
```

#### Results Comparison
| Product Name (Code) | March 2024 Price | October 2024 Price | Price Drift |
| :--- | :--- | :--- | :--- |
| **Sunfeast Cookies 150g (`P100019`)** | **₹62.95** (MRP ₹70.50) | **₹74.65** (MRP ₹83.61) | +₹11.70 (+18.6%) |
| **Britannia Cream Biscuit 60g (`P100049`)** | **₹66.95** (MRP ₹74.98) | **₹68.93** (MRP ₹77.20) | +₹1.98 (+3.0%) |

---

### Task E: Query Across the Two Systems (Engine Proof)

Executed a federated join across MinIO S3 object store and PostgreSQL master tables without prior copying:

```sql
SELECT 
    s.store_name,
    s.city,
    c.category_name,
    round(sum(sales.qty * sales.unit_price), 2) as october_revenue,
    count(distinct sales.bill_no) as bill_count
FROM read_parquet('s3://annapurna-lakehouse/sales/*/*/*.parquet') sales
JOIN pg.stores s 
    ON sales.store_id = s.store_id
JOIN pg.products p 
    ON sales.product_code = p.product_code
    AND sales.business_date >= p.valid_from
    AND sales.business_date <= p.valid_to
JOIN pg.product_categories c 
    ON p.category_id = c.category_id
WHERE sales.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
  AND sales.year_month = '2024-10'
GROUP BY s.store_name, s.city, c.category_name
ORDER BY october_revenue DESC
LIMIT 10;
```

#### Engine Physical Execution Proof (from `EXPLAIN ANALYZE`)
```
┌─────────────────────────────────────┐
│         HTTPFS HTTP Stats           │
│            in: 2.2 MiB              │
│             #HEAD: 32               │
│             #GET: 716               │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│           HASH_GROUP_BY             │
└──────────────────┬──────────────────┘
┌──────────────────┴──────────────────┐
│              HASH_JOIN              │
└────────┬───────────────────┬────────┘
┌────────┴────────┐ ┌────────┴────────┐
│   HASH_JOIN     │ │   TABLE_SCAN    │ -> products (PostgreSQL)
└────────┬────────┘ └─────────────────┘
┌────────┴────────┐
│   TABLE_SCAN    │ -> stores (PostgreSQL)
└─────────────────┘
┌─────────────────┐
│  READ_PARQUET   │ -> s3://annapurna-lakehouse/sales/* (MinIO S3)
│ File Filters:   │    (year_month = '2024-10', Scanned Files: 31/31)
└─────────────────┘
```

#### Where Each Component Evaluated:
1. **Evaluated on PostgreSQL**:
   - `TABLE_SCAN (stores)`: Pushes projection (`store_id`, `store_name`, `city`) over PostgreSQL client protocol.
   - `TABLE_SCAN (products)`: Scans catalog and pushes date validity checks (`valid_from`, `valid_to`).
   - `TABLE_SCAN (product_categories)`: Scans category dimension.
2. **Evaluated on MinIO Object Store**:
   - `READ_PARQUET`: MinIO serves HTTP GET range requests (2.2 MiB across 716 range GETs), retrieving only needed byte offsets and dictionary pages.
3. **Evaluated in DuckDB Engine**:
   - Dynamic partition pruning (`year_month = '2024-10'`) restricting S3 fetches to 31 October files.
   - In-memory vectorized `HASH_JOIN` between Postgres streams and S3 parquet streams.
   - Vectorized `HASH_GROUP_BY` and `TOP_N` sorting.

---

### Task F: Financial Reconciliation Against `finance_monthly.csv`

#### 12-Month Reconciliation Table
| Month | Pipeline Revenue (INR) | Finance Signed-off (INR) | Variance (INR) | Variance % | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **2024-01** | ₹38,446,071.33 | ₹38,446,071.33 | **₹0.00** | 0.0000% | **MATCH** |
| **2024-02** | ₹34,887,085.55 | ₹34,887,085.55 | **₹0.00** | 0.0000% | **MATCH** |
| **2024-03** | ₹41,971,649.09 | ₹42,457,899.09 | **-₹486,250.00** | -1.1453% | **VARIANCE** |
| **2024-04** | ₹37,958,457.37 | ₹37,958,457.37 | **₹0.00** | 0.0000% | **MATCH** |
| **2024-05** | ₹41,764,716.40 | ₹41,764,716.40 | **₹0.00** | 0.0000% | **MATCH** |
| **2024-06** | ₹38,987,082.82 | ₹38,987,082.82 | **₹0.00** | 0.0000% | **MATCH** |
| **2024-07** | ₹40,295,160.11 | ₹40,527,291.81 | **-₹232,131.70** | -0.5728% | **VARIANCE** |
| **2024-08** | ₹45,252,181.75 | ₹45,252,181.75 | **₹0.00** | 0.0000% | **MATCH** |
| **2024-09** | ₹44,615,037.46 | ₹44,615,037.46 | **₹0.00** | 0.0000% | **MATCH** |
| **2024-10** | ₹56,359,195.92 | ₹56,359,195.92 | **₹0.00** | 0.0000% | **MATCH** |
| **2024-11** | ₹51,583,838.47 | ₹51,583,838.47 | **₹0.00** | 0.0000% | **MATCH** |
| **2024-12** | ₹50,745,259.48 | ₹50,745,209.00 | **+₹50.48** | +0.0001% | **VARIANCE** |

#### Root Cause Analysis & Actions for the Finance Team

1. **March 2024 (-₹486,250.00)**:
   - **Classification**: *A difference in how the two of you define revenue* (Revenue Scope).
   - **Root Cause**: Finance signed off ₹42,457,899.09 because they included a manual institutional bulk invoice of exactly ₹486,250.00 invoiced outside the retail POS till system. The retail POS data is complete and accurate for store operations.
   - **Take Back to Finance**: Clarify the scope of retail till reporting vs corporate general ledger. Request an ERP institutional invoice feed to ingest non-till institutional orders into an institutional ledger.

2. **July 2024 (-₹232,131.70)**:
   - **Classification**: *Something wrong with the source data* (Physical Data Gap).
   - **Root Cause**: Store S07 (Pune Baner) experienced a till server hardware failure for 3 days (July 9, 10, and 11, 2024). Files `SALES_S07_20240709`, `SALES_S07_20240710`, and `SALES_S07_20240711` were never exported. The store manager phoned in the ₹232,131.70 total directly to finance.
   - **Take Back to Finance**: Report the physical 3-day outage gap in POS files. Establish a formal manual adjustment journal entry interface in the data lake with store manager sign-off rather than ad-hoc spreadsheet entries.

3. **December 2024 (+₹50.48)**:
   - **Classification**: *A difference in how the two of you define revenue* (Rounding Convention).
   - **Root Cause**: Finance rounded each completed bill to the nearest integer rupee before aggregating (yielding ₹50,745,209.00). The data pipeline computes exact fractional paise line summation before rounding (yielding ₹50,745,259.48). The ₹50.48 variance is accumulated fractional paise across 33,000+ bills.
   - **Take Back to Finance**: Present the mathematical proof that bill-level integer rounding produces ₹50,745,209.00 (0.00 variance) and line-level summation produces ₹50,745,259.48. Request corporate policy sign-off on whether analytical reporting should follow bill-level rounding or unrounded line item summation.
