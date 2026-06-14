"""
Meridian Ops Intelligence — Raw Data Loader
Loads raw CSVs into DuckDB's raw schema. All transformations now live in the
dbt project (see /meridian_dbt) — this script's job is just to get source
data into the warehouse.
"""

import duckdb
import os

DB_PATH  = "data/meridian.duckdb"
DATA_DIR = "data/raw"

RAW_TABLES = {
    "raw.dim_users":          f"{DATA_DIR}/dim_users.csv",
    "raw.fact_events":        f"{DATA_DIR}/fact_events.csv",
    "raw.fact_transactions":  f"{DATA_DIR}/fact_transactions.csv",
    "raw.fact_subscriptions": f"{DATA_DIR}/fact_subscriptions.csv",
    "raw.dim_agents":         f"{DATA_DIR}/dim_agents.csv",
    "raw.fact_disputes":      f"{DATA_DIR}/fact_disputes.csv",
    "raw.fact_aml_alerts":    f"{DATA_DIR}/fact_aml_alerts.csv",
}


def load_raw():
    os.makedirs("data", exist_ok=True)
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    for table, path in RAW_TABLES.items():
        con.execute(f"DROP TABLE IF EXISTS {table}")
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto('{path}')")
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  Loaded {table}: {count:,} rows")

    con.close()
    print(f"\nRaw data loaded into {DB_PATH}")
    print("Next: cd meridian_dbt && dbt run")
    return DB_PATH


if __name__ == "__main__":
    load_raw()
