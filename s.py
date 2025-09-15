import os
import asyncpg

DATABASE_URL = "postgresql://postgres:Airrchip9090@20.244.42.152:5432/frruit_db"

async def print_last_5_trending_stocks():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set in environment.")
        return

    DB_POOL = await asyncpg.create_pool(DATABASE_URL)
    async with DB_POOL.acquire() as connection:
        rows = await connection.fetch("""
            SELECT * FROM trending_stocks_in;
        """)
        print("Last 5 rows from 'trending_dashboard':")
        for row in rows:
            print(dict(row))
    await DB_POOL.close()

# To run the function:
import asyncio
asyncio.run(print_last_5_trending_stocks())

async def create_trending_stocks_table():
    """Creates the trending_stocks table in PostgreSQL if it doesn't exist."""
    DB_POOL = await asyncpg.create_pool(DATABASE_URL)
    async with DB_POOL.acquire() as connection:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS trending_dashboard (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL,
                country_code VARCHAR(10) NOT NULL,
                data JSONB NOT NULL
            );
        """)
        print("INFO: 'trending_stocks' table checked/created successfully.")

# import asyncio
# asyncio.run(create_trending_stocks_table())