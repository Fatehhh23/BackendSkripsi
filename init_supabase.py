import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    # Parse URL without the asyncpg driver part for asyncpg.connect()
    db_url = os.getenv("DATABASE_URL").replace("+asyncpg", "")
    print(f"Connecting to: {db_url}")
    
    conn = await asyncpg.connect(db_url)
    try:
        with open("database_setup.sql", "r", encoding="utf-8") as f:
            sql = f.read()
        
        # We need to remove the "DROP DATABASE" and "CREATE DATABASE" and "\c" commands since Supabase already provides a DB
        # We will split on "CREATE DATABASE" and take everything after the \c tsunami_db
        clean_sql = []
        skip = False
        for line in sql.split('\n'):
            if "DROP DATABASE" in line or "CREATE DATABASE" in line or "WITH OWNER" in line or "LIMIT = -1" in line or "\\ c tsunami_db" in line or "\c tsunami_db" in line:
                continue
            clean_sql.append(line)
            
        final_sql = "\n".join(clean_sql)
        print("Executing SQL setup script...")
        await conn.execute(final_sql)
        print("SUCCESS! Database initialized on Supabase.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
