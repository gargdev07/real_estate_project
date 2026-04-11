"""
Lightweight ORM-based seeder — creates tables and default users only.
For full data loading (CSV -> all 6 tables), use scripts/seed_db.py instead.
"""
from database import engine, Base, SessionLocal
import models
import bcrypt


def hash_password(password: str):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def seed():
    # Create ORM tables (does NOT create materialized views - run schema.sql for those)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Check if users already exist
        if db.query(models.User).first():
            print("Users already exist, skipping seed.")
            return

        # Create default users
        admin = models.User(
            username="admin",
            email="admin@example.com",
            hashed_pw=hash_password("admin123"),
            role="admin",
            is_active=True
        )
        analyst = models.User(
            username="analyst",
            email="analyst@example.com",
            hashed_pw=hash_password("analyst123"),
            role="analyst",
            is_active=True
        )

        db.add(admin)
        db.add(analyst)
        db.commit()
        print("[OK] Database seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seeding failed: {e}")
        raise

    finally:
        db.close()

if __name__ == "__main__":
    seed()