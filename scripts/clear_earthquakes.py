
import sys
import os
import asyncio

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal
from app.models.models import Earthquake
from sqlalchemy import delete, text

async def clear_data():
    print("Connecting to database...")
    async with AsyncSessionLocal() as session:
        print("Clearing earthquakes table...")
        # Use truncate for faster deletion if supported, or delete
        await session.execute(delete(Earthquake))
        await session.commit()
        print("Done! All earthquake data removed form database.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(clear_data())
