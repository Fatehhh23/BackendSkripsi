import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

async def purge():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        print("Menghapus data di tabel inundation_zones...")
        await conn.execute(text("DELETE FROM inundation_zones"))
        print("Menghapus data di tabel simulations...")
        await conn.execute(text("DELETE FROM simulations"))
        print("Semua riwayat simulasi berhasil dihapus.")
        
if __name__ == "__main__":
    asyncio.run(purge())
