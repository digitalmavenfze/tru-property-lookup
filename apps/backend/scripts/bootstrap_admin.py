import os
from passlib.context import CryptContext
import psycopg
from dotenv import load_dotenv

load_dotenv("/app/.env")

DATABASE_URL = os.getenv("DATABASE_URL")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TENANT_NAME = "Tru Property Lookup"
TENANT_SLUG = "tru-property-lookup"
ADMIN_NAME = "Admin User"
ADMIN_EMAIL = "admin@truproplookup.trucrm.io"
ADMIN_PASSWORD = "ChangeMe123!"

def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing")

    password_hash = pwd_context.hash(ADMIN_PASSWORD)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tenants (name, slug)
                VALUES (%s, %s)
                ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
            """, (TENANT_NAME, TENANT_SLUG))
            tenant_id = cur.fetchone()[0]

            cur.execute("""
                SELECT id FROM users
                WHERE tenant_id = %s AND email = %s
            """, (tenant_id, ADMIN_EMAIL))
            existing = cur.fetchone()

            if existing:
                print("Admin user already exists")
            else:
                cur.execute("""
                    INSERT INTO users (tenant_id, full_name, email, password_hash, role)
                    VALUES (%s, %s, %s, %s, %s)
                """, (tenant_id, ADMIN_NAME, ADMIN_EMAIL, password_hash, "admin"))
                print("Admin user created")

        conn.commit()

    print("Bootstrap complete")
    print(f"Admin email: {ADMIN_EMAIL}")
    print(f"Temporary password: {ADMIN_PASSWORD}")

if __name__ == "__main__":
    main()
