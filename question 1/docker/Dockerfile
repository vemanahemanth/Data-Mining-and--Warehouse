FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    duckdb==1.1.3 \
    boto3 \
    psycopg2-binary \
    pandas \
    tabulate

# Pre-install duckdb extensions into root duckdb directory so offline cold start is guaranteed
RUN python -c "import duckdb; con = duckdb.connect(); con.execute('INSTALL httpfs; INSTALL postgres;')"

COPY pipeline/ /app/pipeline/
COPY run_all.py /app/run_all.py

CMD ["python", "run_all.py"]
