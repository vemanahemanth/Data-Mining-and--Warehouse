CREATE TABLE notices (
    notice_id VARCHAR(50) PRIMARY KEY,
    portal_id VARCHAR(10),
    title TEXT,
    body TEXT
);

CREATE TABLE lsh_bands (
    band_id INTEGER,
    hash_value VARCHAR(64),
    notice_id VARCHAR(50) REFERENCES notices(notice_id)
);

CREATE INDEX idx_lsh_lookup ON lsh_bands (band_id, hash_value);
CREATE INDEX idx_lsh_notice ON lsh_bands (notice_id);
