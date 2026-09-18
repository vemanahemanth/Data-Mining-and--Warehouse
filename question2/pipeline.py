import os
import re
import time
import pandas as pd
from datasketch import MinHash
import psycopg2
from sqlalchemy import create_engine

print("--- TENDER DEDUPLICATION PIPELINE START ---")

DATA_DIR = "/exam/data"
NOTICES_DIR = os.path.join(DATA_DIR, "notices")
LABELS_PATH = os.path.join(DATA_DIR, "labelled_pairs.csv")

# If running outside docker for local tests, adjust paths
if not os.path.exists(DATA_DIR):
    DATA_DIR = "./data_2"
    NOTICES_DIR = os.path.join(DATA_DIR, "notices")
    LABELS_PATH = os.path.join(DATA_DIR, "labelled_pairs.csv")

import glob

print(f"Loading data from {DATA_DIR}...")
# Load labeled pairs
labels_df = pd.read_csv(LABELS_PATH)

# Load notices
csv_files = glob.glob(os.path.join(NOTICES_DIR, "*.csv"))
notices_df = pd.concat([pd.read_csv(f) for f in csv_files], ignore_index=True)

# Fill na in body
notices_df['body'] = notices_df['body'].fillna('')

print(f"Loaded {len(notices_df)} notices and {len(labels_df)} labeled pairs.")

print("\n=== Section A: From an intractable comparison to tractable one ===")
# A) Define what "similar" means
# We strip common nodal aggregator boilerplate and dates/money.
BOILERPLATES = [
    "NATIONAL PROCUREMENT AGGREGATION SERVICE",
    "STATE PROCUREMENT CELL"
]

def clean_text(text):
    text = str(text).upper()
    for bp in BOILERPLATES:
        text = text.replace(bp, "")
    # Remove dates and money (numbers basically)
    text = re.sub(r'\d+', '', text)
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

print("Cleaning texts...")
notices_df['cleaned_body'] = notices_df['body'].apply(clean_text)

def get_shingles(text, k=3):
    return set([text[i:i+k] for i in range(len(text) - k + 1)])

def jaccard(s1, s2):
    if not s1 or not s2: return 0.0
    return len(s1.intersection(s2)) / len(s1.union(s2))

# Evaluate on labels
print("Evaluating score separation on labeled pairs...")
# Merge to get texts
merged_labels = labels_df.copy()
merged_labels = merged_labels.merge(notices_df[['notice_id', 'cleaned_body']], left_on='notice_id_a', right_on='notice_id', how='left')
merged_labels.rename(columns={'cleaned_body': 'cleaned_body_a'}, inplace=True)
merged_labels.drop('notice_id', axis=1, inplace=True)

merged_labels = merged_labels.merge(notices_df[['notice_id', 'cleaned_body']], left_on='notice_id_b', right_on='notice_id', how='left')
merged_labels.rename(columns={'cleaned_body': 'cleaned_body_b'}, inplace=True)
merged_labels.drop('notice_id', axis=1, inplace=True)

merged_labels['shingles_a'] = merged_labels['cleaned_body_a'].apply(lambda x: get_shingles(str(x)))
merged_labels['shingles_b'] = merged_labels['cleaned_body_b'].apply(lambda x: get_shingles(str(x)))
merged_labels['jaccard'] = merged_labels.apply(lambda row: jaccard(row['shingles_a'], row['shingles_b']), axis=1)

same_avg = merged_labels[merged_labels['label'] == 'same']['jaccard'].mean()
diff_avg = merged_labels[merged_labels['label'] == 'different']['jaccard'].mean()

print(f"Average Jaccard for 'same': {same_avg:.3f}")
print(f"Average Jaccard for 'different': {diff_avg:.3f}")

print("\n=== Section B: Trade Exactness for space ===")
# B) MinHash
NUM_PERM = 126
print(f"Generating MinHashes with {NUM_PERM} permutations...")
def get_minhash(shingles):
    m = MinHash(num_perm=NUM_PERM)
    for s in shingles:
        m.update(s.encode('utf8'))
    return m

merged_labels['minhash_a'] = merged_labels['shingles_a'].apply(get_minhash)
merged_labels['minhash_b'] = merged_labels['shingles_b'].apply(get_minhash)
merged_labels['mh_estimate'] = merged_labels.apply(lambda row: row['minhash_a'].jaccard(row['minhash_b']), axis=1)
error = (merged_labels['jaccard'] - merged_labels['mh_estimate']).abs().mean()
print(f"Mean Absolute Error of MinHash estimator: {error:.4f}")


print("\n=== Section C: Make Retrieval sublinear, and price the risk ===")
# C) LSH bands
BANDS = 14
ROWS = 9
# Threshold ~ (1/b)^(1/r) = (1/14)^(1/9) = 0.729
print(f"Using {BANDS} bands of {ROWS} rows.")
print(f"Estimated similarity threshold: {(1.0/BANDS)**(1.0/ROWS):.3f}")
print("This heavily penalizes false positives (which cause lawsuits) by requiring high similarity to survive to the candidate stage.")

# Generate MinHashes for all
print("Computing MinHashes for full corpus...")
notices_df['shingles'] = notices_df['cleaned_body'].apply(lambda x: get_shingles(str(x)))
notices_df['minhash'] = notices_df['shingles'].apply(get_minhash)


print("\n=== Section D: Given the retrieval structure a home and an access path ===")
db_host = os.environ.get('DB_HOST', 'localhost')
db_user = os.environ.get('DB_USER', 'tender_user')
db_password = os.environ.get('DB_PASSWORD', 'tender_password')
db_name = os.environ.get('DB_NAME', 'tenders')

try:
    conn = psycopg2.connect(host=db_host, user=db_user, password=db_password, dbname=db_name)
    conn.autocommit = True
    cursor = conn.cursor()
    print("Connected to Database.")
    
    # Clear existing data to allow safe reruns
    cursor.execute("TRUNCATE TABLE lsh_bands, notices CASCADE")
    
    # Insert notices
    print("Inserting notices...")
    engine = create_engine(f'postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}')
    notices_df[['notice_id', 'portal_id', 'title', 'body']].to_sql('notices', engine, if_exists='append', index=False)
    
    # Generate and insert bands
    print("Generating LSH bands...")
    bands_data = []
    for idx, row in notices_df.iterrows():
        nid = row['notice_id']
        hashvalues = row['minhash'].hashvalues
        for b in range(BANDS):
            band_hash = hash(tuple(hashvalues[b*ROWS:(b+1)*ROWS]))
            bands_data.append((b, str(band_hash), nid))
            
    bands_df = pd.DataFrame(bands_data, columns=['band_id', 'hash_value', 'notice_id'])
    print("Inserting LSH bands to DB...")
    bands_df.to_sql('lsh_bands', engine, if_exists='append', index=False)
    
    # Performance testing
    print("Testing Access Path Performance...")
    # Find a sample candidate
    sample_b = bands_data[0][0]
    sample_h = bands_data[0][1]
    
    # With index
    start_t = time.time()
    cursor.execute(f"EXPLAIN ANALYZE SELECT notice_id FROM lsh_bands WHERE band_id = {sample_b} AND hash_value = '{sample_h}'")
    indexed_plan = cursor.fetchall()
    indexed_time = time.time() - start_t
    
    # Without index
    cursor.execute("DROP INDEX IF EXISTS idx_lsh_lookup")
    start_t = time.time()
    cursor.execute(f"EXPLAIN ANALYZE SELECT notice_id FROM lsh_bands WHERE band_id = {sample_b} AND hash_value = '{sample_h}'")
    seq_plan = cursor.fetchall()
    seq_time = time.time() - start_t
    
    # Recreate index
    cursor.execute("CREATE INDEX idx_lsh_lookup ON lsh_bands (band_id, hash_value)")
    
    print(f"Indexed query wall-clock time: {indexed_time:.4f}s")
    print(f"Sequential Scan wall-clock time: {seq_time:.4f}s")
    
    print("\n=== Section E: Find the place where the design betrays you ===")
    # Skew mitigation
    print("Checking for skewed buckets (hotspots)...")
    cursor.execute("SELECT band_id, hash_value, COUNT(notice_id) as cnt FROM lsh_bands GROUP BY band_id, hash_value ORDER BY cnt DESC LIMIT 5")
    hotspots = cursor.fetchall()
    print("Top 5 largest LSH buckets:")
    for h in hotspots:
        print(f"Band: {h[0]}, Hash: {h[1]}, Size: {h[2]}")
        
    print("Mechanical Cause: Very short notices are overwhelmed by the exact same nodal aggregator boilerplate (like P001), causing identical MinHashes.")
    print("Mitigation: We ignore buckets larger than 100 items to protect the 20-minute budget. We must measure the cost in retrieval quality.")
    
    # Calculate retrieval quality before and after on the labelled 'same' pairs
    same_pairs = labels_df[labels_df['label'] == 'same']
    retrieved_before = 0
    retrieved_after = 0
    
    for _, row in same_pairs.iterrows():
        id_a, id_b = row['notice_id_a'], row['notice_id_b']
        # Check if they share a band
        cursor.execute(f"SELECT band_id, hash_value FROM lsh_bands WHERE notice_id = '{id_a}' INTERSECT SELECT band_id, hash_value FROM lsh_bands WHERE notice_id = '{id_b}'")
        shared_bands = cursor.fetchall()
        
        if len(shared_bands) > 0:
            retrieved_before += 1
            # Check if they share a band that is NOT a hotspot
            valid_after = False
            for b_id, h_val in shared_bands:
                cursor.execute(f"SELECT COUNT(notice_id) FROM lsh_bands WHERE band_id = {b_id} AND hash_value = '{h_val}'")
                cnt = cursor.fetchone()[0]
                if cnt <= 100:
                    valid_after = True
                    break
            if valid_after:
                retrieved_after += 1
                
    recall_before = retrieved_before / len(same_pairs)
    recall_after = retrieved_after / len(same_pairs)
    print(f"Retrieval Recall (Before Mitigation): {recall_before:.3f}")
    print(f"Retrieval Recall (After Mitigation): {recall_after:.3f}")
    print(f"Mitigation cost: {(recall_before - recall_after) * 100:.1f}% drop in recall of true duplicates.")
    
except Exception as e:
    print(f"Database error: {e}")

print("--- TENDER DEDUPLICATION PIPELINE END ---")
