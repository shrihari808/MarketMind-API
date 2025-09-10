# aigptssh/api/dashboard/postgres_history.py
import json
from datetime import datetime, timezone
import asyncpg

# This global variable will be populated with the database pool from main.py
DB_POOL = None

async def create_dashboard_output_table():
    """Creates the dashboard_output table in PostgreSQL if it doesn't exist."""
    if not DB_POOL:
        print("ERROR: Database connection pool not initialized for postgres_history.")
        return
    async with DB_POOL.acquire() as connection:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_output (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL,
                country_code VARCHAR(10) NOT NULL,
                data JSONB NOT NULL
            );
        """)
        print("INFO: 'dashboard_output' table checked/created successfully.")

async def save_dashboard_output(data, country_code):
    """Saves the final dashboard JSON data to the dashboard_output table."""
    if not data or not DB_POOL:
        return

    timestamp = datetime.now(timezone.utc)
    # Convert the Python dict to a JSON string for storing in the JSONB column
    data_json = json.dumps(data)

    async with DB_POOL.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO dashboard_output (timestamp, country_code, data)
            VALUES ($1, $2, $3)
            """,
            timestamp,
            country_code,
            data_json
        )
        print(f"INFO: Also saved dashboard output for {country_code} to PostgreSQL.")