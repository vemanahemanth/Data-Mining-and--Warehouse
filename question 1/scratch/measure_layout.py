import glob
import os

all_files = glob.glob('data/sales/*')
total_bytes_raw = sum(os.path.getsize(f) for f in all_files)
print(f"Total raw files: {len(all_files)}")
print(f"Total raw bytes: {total_bytes_raw} bytes ({total_bytes_raw / (1024*1024):.2f} MB)")

# S01 in 2024-10
s01_oct_files = glob.glob('data/sales/SALES_S01_202410*.csv')
s01_oct_bytes = sum(os.path.getsize(f) for f in s01_oct_files)
print(f"S01 Oct 2024 raw files: {len(s01_oct_files)}")
print(f"S01 Oct 2024 raw bytes: {s01_oct_bytes} bytes ({s01_oct_bytes / 1024:.2f} KB)")

# All stores in 2024-10
oct_files = glob.glob('data/sales/SALES_*_202410*.csv')
print(f"All stores Oct 2024 files: {len(oct_files)}")
print(f"All stores Oct 2024 bytes: {sum(os.path.getsize(f) for f in oct_files)} bytes")
