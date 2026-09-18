#!/bin/bash
mc alias set local http://annapurna-minio:9000 minioadmin minioadmin
echo ""
echo "=== Bucket structure (store partitions) ==="
mc ls local/annapurna-lakehouse/sales/
echo ""
echo "=== S01 months ==="
mc ls "local/annapurna-lakehouse/sales/store_id=S01/"
echo ""
echo "=== S01 October 2024 files ==="
mc ls "local/annapurna-lakehouse/sales/store_id=S01/year_month=2024-10/"
echo ""
echo "=== File count and size for S01 October 2024 ==="
mc ls "local/annapurna-lakehouse/sales/store_id=S01/year_month=2024-10/" | wc -l
mc du "local/annapurna-lakehouse/sales/store_id=S01/year_month=2024-10/"
echo ""
echo "=== Total bucket usage ==="
mc du local/annapurna-lakehouse/
