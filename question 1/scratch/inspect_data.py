import os
import glob
import re
import duckdb
import pandas as pd

con = duckdb.connect()

s01_files = glob.glob('data/sales/SALES_S01_*.csv')
s06_files = glob.glob('data/sales/SALES_S06_*.csv')
s10_files = glob.glob('data/sales/SALES_S10_*.csv')

print("S01 sample:")
print(con.execute("SELECT * FROM read_csv(?, header=true) LIMIT 2", [s01_files[0]]).df())

print("\nS06 sample:")
print(con.execute("SELECT * FROM read_csv(?, delim=';', header=true) LIMIT 2", [s06_files[0]]).df())

print("\nS10 sample:")
print(con.execute("SELECT * FROM read_csv(?, header=true) LIMIT 2", [s10_files[0]]).df())
