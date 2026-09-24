# aigptssh/api/dashboard/postgres_history.py
import json
from datetime import datetime, timezone
import asyncpg

# This global variable will be populated with the database pool from main.py
DB_POOL = None

async def create_dashboard_tables():
    """Creates all dashboard-related tables in PostgreSQL if they don't exist."""
    if not DB_POOL:
        print("ERROR: Database connection pool not initialized for postgres_history.")
        return
    async with DB_POOL.acquire() as connection:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS trending_dashboard_in (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL,
                country_code VARCHAR(10) NOT NULL,
                data JSONB NOT NULL
            );
        """)
        print("INFO: 'trending_dashboard_in' table checked/created successfully.")
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS trending_dashboard_us (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL,
                country_code VARCHAR(10) NOT NULL,
                data JSONB NOT NULL
            );
        """)
        print("INFO: 'trending_dashboard_us' table checked/created successfully.")
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS trending_stocks_in (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL,
                country_code VARCHAR(10) NOT NULL,
                data JSONB NOT NULL
            );
        """)
        print("INFO: 'trending_stocks_in' table checked/created successfully.")
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS trending_stocks_us (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL,
                country_code VARCHAR(10) NOT NULL,
                data JSONB NOT NULL
            );
        """)
        print("INFO: 'trending_stocks_us' table checked/created successfully.")


async def save_dashboard_output(data, country_code):
    """
    Clears the existing data and saves the new dashboard JSON data to the
    appropriate country-specific table, ensuring only the latest data is present.
    """
    if not data or not DB_POOL:
        return

    timestamp = datetime.now(timezone.utc)
    data_json = json.dumps(data)
    table_name = f"trending_dashboard_{country_code.lower()}"

    async with DB_POOL.acquire() as connection:
        async with connection.transaction():
            # Truncate the table to clear all existing data
            await connection.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY;")
            
            # Insert the new, single row of data
            await connection.execute(
                f"""
                INSERT INTO {table_name} (timestamp, country_code, data)
                VALUES ($1, $2, $3)
                """,
                timestamp,
                country_code,
                data_json
            )
    print(f"INFO: Cleared and saved dashboard output for {country_code} to PostgreSQL table {table_name}.")

async def save_trending_stocks_output(data, country_code):
    """
    Clears the existing data and saves the new trending stocks JSON data to the
    appropriate country-specific table, ensuring only the latest data is present.
    """
    if not data or not DB_POOL:
        return

    timestamp = datetime.now(timezone.utc)
    data_json = json.dumps(data)
    table_name = f"trending_stocks_{country_code.lower()}"

    async with DB_POOL.acquire() as connection:
        async with connection.transaction():
            # Truncate the table to clear all existing data
            await connection.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY;")
            
            # Insert the new, single row of data
            await connection.execute(
                f"""
                INSERT INTO {table_name} (timestamp, country_code, data)
                VALUES ($1, $2, $3)
                """,
                timestamp,
                country_code,
                data_json
            )
    print(f"INFO: Cleared and saved trending stocks for {country_code} to PostgreSQL table {table_name}.")