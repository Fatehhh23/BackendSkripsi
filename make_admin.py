import asyncio
import sys
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Add parent directory to path to allow importing app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.models import User, UserRole
from app.config import settings

# Use default settings (for Docker execution)
DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

print(f"Connecting to database at: {DATABASE_URL}")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def promote_user_to_admin():
    print("=== PROMOTE USER TO ADMIN ===")
    email = input("Masukkan Email User yang ingin dijadikan Admin: ").strip()

    if not email:
        print("Email tidak boleh kosong.")
        return

    try:
        async with AsyncSessionLocal() as session:
            # Find user
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user:
                print(f"❌ User dengan email '{email}' TIDAK DITEMUKAN di database.")
                print("Pastikan Anda sudah REGISTER dulu lewat website.")
                return

            # Check current role
            print(f"User ditemukan: {user.username} (Role saat ini: {user.role})")

            if user.role == UserRole.ADMIN:
                print("✅ User ini SUDAH menjadi Admin.")
                return

            # Update role
            confirm = input(f"Yakin ingin mengubah {user.username} menjadi ADMIN? (y/n): ").lower()
            if confirm == 'y':
                user.role = UserRole.ADMIN
                await session.commit()
                print(f"🎉 SUKSES! User '{user.username}' sekarang adalah ADMIN.")
                print("Silakan Logout dan Login ulang di website untuk melihat menu Admin.")
            else:
                print("Batal.")
    except Exception as e:
        print(f"❌ Terjadi kesalahan: {str(e)}")
        print("Pastikan Backend/Database menyala dan bisa diakses via localhost:5432")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(promote_user_to_admin())
