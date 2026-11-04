from app.db.session import SessionLocal, engine, Base
from app.models.user import User
from sqlalchemy import text

def test_field_encryption():
    db = SessionLocal()
    try:
        # 1. Insert user with sensitive encrypted fields
        user = User(
            email="student@riphah.edu.pk",
            hashed_password="hashed_pass_sample",
            full_name="Syeda Ayesha Fatima",
            phone_number="+923001234567"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print("\n--- 1. Python Object (Auto-Decrypted) ---")
        print(f"User ID: {user.id}")
        print(f"Full Name: {user.full_name}")
        print(f"Phone: {user.phone_number}")

        # 2. Query raw database row directly using SQL to verify encryption at rest
        with engine.connect() as conn:
            raw_row = conn.execute(
                text("SELECT id, email, full_name, phone_number FROM users WHERE id = :id"),
                {"id": user.id}
            ).mappings().fetchone()

            print("\n--- 2. Raw PostgreSQL Storage (Encrypted At Rest) ---")
            print(f"Raw full_name in DB: {raw_row['full_name']}")
            print(f"Raw phone_number in DB: {raw_row['phone_number']}")

            assert raw_row['full_name'] != "Syeda Ayesha Fatima"
            assert "gAAAAA" in raw_row['full_name']  # Fernet token prefix check
            print("\n✅ US-11.2 Field-Level Encryption Verified Successfully!")

    finally:
        db.close()

if __name__ == "__main__":
    test_field_encryption()