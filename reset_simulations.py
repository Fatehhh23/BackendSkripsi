
import asyncio
import os
import sys

# Tambahkan current directory ke python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database.models import Simulation

# Manually define localhost connection for script execution
# Using credentials from .env: tsunami_user:tsunami_password
DATABASE_URL = "postgresql+asyncpg://tsunami_user:tsunami_password@localhost:5432/tsunami_db"

print(f"Connecting to: {DATABASE_URL}")

try:
    engine = create_async_engine(
        DATABASE_URL,
        echo=True,
    )
except Exception as e:
    print(f"Error creating engine: {e}")
    sys.exit(1)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def reset_simulations():
    """Menghapus SEMUA riwayat simulasi dari database."""
    print("Membuka koneksi database...")
    
    async with AsyncSessionLocal() as session:
        try:
            print("Menghapus semua data simulasi...")
            stmt = delete(Simulation)
            result = await session.execute(stmt)
            await session.commit()
            
            print(f"Berhasil! {result.rowcount} simulasi telah dihapus.")
            print("Total simulasi sekarang: 0")
            
        except Exception as e:
            await session.rollback()
            print(f"Gagal menghapus simulasi: {e}")
            sys.exit(1)
        finally:
            await session.close()

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset Simulations")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    if args.force:
        asyncio.run(reset_simulations())
        asyncio.run(engine.dispose())
    else:
        confirm = input("PERINGATAN: Ini akan menghapus SEMUA riwayat simulasi untuk SEMUA user.\nApakah Anda yakin? (y/n): ")
        if confirm.lower() == 'y':
            asyncio.run(reset_simulations())
            # Cleanup engine
            asyncio.run(engine.dispose())
        else:
            print("Operasi dibatalkan.")
