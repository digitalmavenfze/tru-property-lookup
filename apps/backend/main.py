import os
import secrets
import hashlib
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import psycopg
from dotenv import load_dotenv

load_dotenv("/app/.env")

app = FastAPI(title="Tru Property Lookup API")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DATABASE_URL = os.getenv("DATABASE_URL")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_user_from_auth(authorization: str | None):
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    raw_token = authorization.replace("Bearer ", "", 1).strip()
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing session token")

    token_hash = hash_session_token(raw_token)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    u.id,
                    u.full_name,
                    u.email,
                    u.role,
                    u.status,
                    t.name
                FROM active_sessions s
                JOIN users u ON u.id = s.user_id
                JOIN tenants t ON t.id = u.tenant_id
                WHERE s.session_token_hash = %s
                  AND s.is_revoked = FALSE
                LIMIT 1
            """, (token_hash,))
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=401, detail="Session is invalid or expired")

            user_id, full_name, email, role, status, tenant_name = row

            if status != "active":
                raise HTTPException(status_code=403, detail="User is not active")

            cur.execute("""
                UPDATE active_sessions
                SET last_seen_at = NOW()
                WHERE session_token_hash = %s
            """, (token_hash,))
        conn.commit()

    return {
        "id": str(user_id),
        "full_name": full_name,
        "email": email,
        "role": role,
        "tenant": tenant_name
    }


@app.get("/")
def root():
    return {
        "app": "Tru Property Lookup API",
        "status": "ok"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/login")
def login(payload: LoginRequest):
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.full_name, u.email, u.password_hash, u.role, u.status, t.name
                FROM users u
                JOIN tenants t ON t.id = u.tenant_id
                WHERE LOWER(u.email) = LOWER(%s)
                LIMIT 1
            """, (payload.email,))
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=401, detail="Invalid email or password")

            user_id, full_name, email, password_hash, role, status, tenant_name = row

            if status != "active":
                raise HTTPException(status_code=403, detail="User is not active")

            if not pwd_context.verify(payload.password, password_hash):
                raise HTTPException(status_code=401, detail="Invalid email or password")

            cur.execute("""
                UPDATE active_sessions
                SET is_revoked = TRUE, revoked_at = NOW()
                WHERE user_id = %s AND is_revoked = FALSE
            """, (user_id,))

            raw_token = secrets.token_urlsafe(32)
            token_hash = hash_session_token(raw_token)

            cur.execute("""
                INSERT INTO active_sessions (user_id, session_token_hash, is_revoked)
                VALUES (%s, %s, FALSE)
            """, (user_id, token_hash))

        conn.commit()

    return {
        "message": "Login successful",
        "session_token": raw_token,
        "user": {
            "id": str(user_id),
            "full_name": full_name,
            "email": email,
            "role": role,
            "tenant": tenant_name
        }
    }


@app.get("/me")
def me(authorization: str | None = Header(default=None)):
    user = get_current_user_from_auth(authorization)
    return {
        "message": "Session valid",
        "user": user
    }
