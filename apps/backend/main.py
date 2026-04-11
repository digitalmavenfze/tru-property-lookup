
import os
import re
import json
from datetime import datetime, timezone, timedelta
import secrets
import hashlib
from typing import Any
from io import BytesIO

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Query
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import psycopg
from dotenv import load_dotenv
import pandas as pd

load_dotenv("/app/.env")

app = FastAPI(title="Tru Property Lookup API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://72.61.117.207:3020",
        "http://127.0.0.1:3020",
        "http://localhost:3020",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DATABASE_URL = os.getenv("DATABASE_URL")


BILLING_PLANS = {
    "starter": {
        "name": "Starter",
        "monthly_credits": 200,
        "price_usd": 49.0,
        "features": {
            "export": False,
            "ai_search": True,
            "owner_detail": True,
        },
    },
    "pro": {
        "name": "Pro",
        "monthly_credits": 5000,
        "price_usd": 199.0,
        "features": {
            "export": True,
            "ai_search": True,
            "owner_detail": True,
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "monthly_credits": 25000,
        "price_usd": 299.0,
        "features": {
            "export": True,
            "ai_search": True,
            "owner_detail": True,
        },
    },
}



BILLING_PLANS = {
    "starter": {
        "name": "Starter",
        "monthly_credits": 200,
        "price_usd": 49.0,
        "features": {
            "export": False,
            "ai_search": True,
            "owner_detail": True,
        },
    },
    "pro": {
        "name": "Pro",
        "monthly_credits": 5000,
        "price_usd": 199.0,
        "features": {
            "export": True,
            "ai_search": True,
            "owner_detail": True,
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "monthly_credits": 25000,
        "price_usd": 299.0,
        "features": {
            "export": True,
            "ai_search": True,
            "owner_detail": True,
        },
    },
}
UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SheetMappingItem(BaseModel):
    sheet_id: str
    mappings: dict[str, str]


class FinalizeImportRequest(BaseModel):
    uploaded_file_id: str
    sheets: list[SheetMappingItem]
    duplicate_action: str | None = None


REQUIRED_SYSTEM_FIELDS = {
    "property_building_name",
    "property_unit_number",
}

SYSTEM_FIELDS = {
    "owner_full_name",
    "property_plot_number",
    "property_p_number",
    "property_municipality_number",
    "owner_first_name",
    "owner_last_name",
    "owner_email",
    "owner_phone",
    "owner_mailing_address",
    "owner_nationality",
    "property_city",
    "property_district",
    "property_master_community",
    "property_community",
    "property_building_name",
    "property_villa_name",
    "property_unit_number",
    "property_type",
    "property_developer_name",
    "transaction_type",
    "transaction_date",
    "transaction_price",
    "transaction_currency",
    "transaction_notes",
}




class SheetMappingItem(BaseModel):
    sheet_id: str
    mappings: dict[str, str]


class FinalizeImportRequest(BaseModel):
    uploaded_file_id: str
    sheets: list[SheetMappingItem]
    duplicate_action: str | None = None




def normalize_header_name(header: str | None) -> str:
    if header is None:
        return ""
    value = str(header).strip()
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).lower()


def reset_monthly_usage_if_needed(cur, user_id: str):
    cur.execute(
        """
        SELECT credits_reset_at, plan_code
        FROM users
        WHERE id = %s
        """,
        (user_id,),
    )
    row = cur.fetchone()
    if not row:
        return

    credits_reset_at, plan_code = row
    if credits_reset_at and credits_reset_at > datetime.now(timezone.utc):
        return

    cur.execute(
        """
        SELECT monthly_credits, monthly_search_limit
        FROM subscription_plans
        WHERE code = %s
        """,
        (plan_code or "starter",),
    )
    plan = cur.fetchone()
    monthly_credits = plan[0] if plan else 200
    monthly_limit = plan[1] if plan else 200

    cur.execute(
        """
        UPDATE users
        SET
            credits_balance = %s,
            monthly_search_count = 0,
            monthly_search_limit = %s,
            credits_reset_at = NOW() + INTERVAL '30 days'
        WHERE id = %s
        """,
        (monthly_credits, monthly_limit, user_id),
    )


def detect_area_tier_and_cost(cur, text_parts: list[str]):
    haystack = " ".join([clean_text(x).lower() for x in text_parts if clean_text(x)])
    if not haystack:
        return ("standard", 1, "")

    cur.execute(
        """
        SELECT area_key, area_tier, credit_cost
        FROM premium_areas
        WHERE is_active = true
        ORDER BY credit_cost DESC, area_key
        """
    )
    for area_key, area_tier, credit_cost in cur.fetchall():
        if area_key in haystack:
            return (area_tier or "premium", int(credit_cost or 1), area_key)

    return ("standard", 1, "")


def consume_credits_and_log(
    cur,
    user: dict,
    endpoint: str,
    query_text: str = "",
    owner_name: str = "",
    phone: str = "",
    email: str = "",
    unit_number: str = "",
    project_name: str = "",
    property_type: str = "",
    result_count: int = 0,
    metadata: dict | None = None,
):
    metadata = metadata or {}

    reset_monthly_usage_if_needed(cur, str(user["id"]))

    area_tier, credits_used, matched_area_key = detect_area_tier_and_cost(
        cur,
        [
            query_text,
            owner_name,
            phone,
            email,
            unit_number,
            project_name,
            property_type,
            metadata.get("master_community", ""),
            metadata.get("district", ""),
            metadata.get("sub_community", ""),
        ],
    )

    cur.execute(
        """
        SELECT credits_balance, monthly_search_count, monthly_search_limit, billing_status, is_superadmin
        FROM users
        WHERE id = %s
        """,
        (str(user["id"]),),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="User not found")

    credits_balance, monthly_search_count, monthly_search_limit, billing_status, is_superadmin = row

    if not is_superadmin:
        if billing_status != "active":
            raise HTTPException(status_code=402, detail="Billing status is not active")
        if monthly_search_limit and monthly_search_count >= monthly_search_limit:
            raise HTTPException(status_code=402, detail="Monthly search limit reached")
        if credits_balance < credits_used:
            raise HTTPException(status_code=402, detail="Not enough credits")

        new_balance = credits_balance - credits_used

        cur.execute(
            """
            UPDATE users
            SET
                credits_balance = %s,
                monthly_search_count = monthly_search_count + 1
            WHERE id = %s
            """,
            (new_balance, str(user["id"])),
        )

        cur.execute(
            """
            INSERT INTO credit_transactions (
                tenant_id,
                user_id,
                transaction_type,
                credits,
                balance_after,
                reason,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                str(user["tenant_id"]),
                str(user["id"]),
                "debit",
                credits_used,
                new_balance,
                f"{endpoint} search usage",
                json.dumps({
                    "endpoint": endpoint,
                    "query_text": query_text,
                    "matched_area_key": matched_area_key,
                    "result_count": result_count,
                    **metadata,
                }),
            ),
        )
    else:
        new_balance = credits_balance

    cur.execute(
        """
        INSERT INTO search_usage_logs (
            tenant_id,
            user_id,
            endpoint,
            query_text,
            owner_name,
            phone,
            email,
            unit_number,
            project_name,
            property_type,
            credits_used,
            result_count,
            area_tier,
            status,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            str(user["tenant_id"]),
            str(user["id"]),
            endpoint,
            query_text,
            owner_name,
            phone,
            email,
            unit_number,
            project_name,
            property_type,
            credits_used if not is_superadmin else 0,
            result_count,
            area_tier,
            "success",
            json.dumps({
                "matched_area_key": matched_area_key,
                "is_superadmin": bool(is_superadmin),
                **metadata,
            }),
        ),
    )

    return {
        "credits_used": 0 if is_superadmin else credits_used,
        "credits_balance": new_balance,
        "area_tier": area_tier,
        "matched_area_key": matched_area_key,
    }


@app.get("/billing/me")
def billing_me(
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)

    plan_code = clean_text(user.get("plan_code") or "starter").lower() or "starter"
    plan = BILLING_PLANS.get(plan_code, BILLING_PLANS["starter"])

    return {
        "plan_code": plan_code,
        "credits_balance": int(user.get("credits_balance", 0) or 0),
        "monthly_search_count": int(user.get("monthly_search_count", 0) or 0),
        "monthly_search_limit": int(user.get("monthly_search_limit", plan.get("monthly_credits", 0)) or 0),
        "credits_reset_at": user.get("credits_reset_at"),
        "billing_status": user.get("billing_status", "active"),
        "is_superadmin": bool(user.get("is_superadmin", False)),
        "plan_name": plan.get("name"),
        "plan_monthly_credits": int(plan.get("monthly_credits", 0) or 0),
        "plan_price_usd": float(plan.get("price_usd", 0) or 0),
        "features": plan.get("features", {}) or {},
    }

@app.get("/billing/usage")
def billing_usage(
    limit: int = Query(default=20, ge=1, le=200),
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    endpoint,
                    query_text,
                    owner_name,
                    phone,
                    email,
                    unit_number,
                    project_name,
                    property_type,
                    credits_used,
                    result_count,
                    area_tier,
                    status,
                    metadata,
                    created_at
                FROM search_usage_logs
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (str(user["id"]), limit),
            )
            rows = cur.fetchall()

    return {
        "results": [
            {
                "id": str(r[0]),
                "endpoint": r[1],
                "query_text": r[2] or "",
                "owner_name": r[3] or "",
                "phone": r[4] or "",
                "email": r[5] or "",
                "unit_number": r[6] or "",
                "project_name": r[7] or "",
                "property_type": r[8] or "",
                "credits_used": int(r[9] or 0),
                "result_count": int(r[10] or 0),
                "area_tier": r[11] or "standard",
                "status": r[12] or "",
                "metadata": r[13] or {},
                "created_at": r[14].isoformat() if r[14] else None,
            }
            for r in rows
        ]
    }



@app.get("/admin/users")
def admin_list_users(
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)
    if not user.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin access required")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    full_name,
                    email,
                    role,
                    tenant_id,
                    plan_code,
                    credits_balance,
                    monthly_search_count,
                    monthly_search_limit,
                    credits_reset_at,
                    billing_status,
                    is_superadmin,
                    created_at
                FROM users
                ORDER BY created_at DESC NULLS LAST, email ASC
                """
            )
            rows = cur.fetchall()

    results = []
    for r in rows:
        results.append({
            "id": str(r[0]),
            "full_name": r[1] or "",
            "email": r[2] or "",
            "role": r[3] or "",
            "tenant_id": str(r[4]) if r[4] else "",
            "plan_code": r[5] or "",
            "credits_balance": int(r[6] or 0),
            "monthly_search_count": int(r[7] or 0),
            "monthly_search_limit": int(r[8] or 0),
            "credits_reset_at": r[9].isoformat() if r[9] else None,
            "billing_status": r[10] or "",
            "is_superadmin": bool(r[11]),
            "created_at": r[12].isoformat() if r[12] else None,
        })

    return {"results": results}







@app.post("/admin/users/{target_user_id}/plan")
def admin_update_user_plan(
    target_user_id: str,
    payload: dict,
    authorization: str | None = Header(default=None),
):
    admin_user = get_current_user_from_auth(authorization)
    if not admin_user.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin access required")

    plan_code = clean_text((payload or {}).get("plan_code", "")).lower()
    billing_status = clean_text((payload or {}).get("billing_status", "active")).lower()

    if plan_code not in BILLING_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan_code")

    if billing_status not in {"active", "paused", "cancelled", "past_due"}:
        raise HTTPException(status_code=400, detail="Invalid billing_status")

    plan = BILLING_PLANS.get(plan_code, BILLING_PLANS["starter"])
    monthly_credits = int(plan.get("monthly_credits", 0))

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET
                    plan_code = %s,
                    monthly_search_limit = %s,
                    billing_status = %s
                WHERE id = %s::uuid
                RETURNING
                    id,
                    full_name,
                    email,
                    plan_code,
                    credits_balance,
                    monthly_search_count,
                    monthly_search_limit,
                    credits_reset_at,
                    billing_status,
                    is_superadmin
                """,
                (plan_code, monthly_credits, billing_status, target_user_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
        conn.commit()

    return {
        "message": "Plan updated",
        "user": {
            "id": str(row[0]),
            "full_name": row[1] or "",
            "email": row[2] or "",
            "plan_code": row[3] or "",
            "credits_balance": int(row[4] or 0),
            "monthly_search_count": int(row[5] or 0),
            "monthly_search_limit": int(row[6] or 0),
            "credits_reset_at": row[7].isoformat() if row[7] else None,
            "billing_status": row[8] or "",
            "is_superadmin": bool(row[9]),
        },
    }




@app.post("/admin/users/{target_user_id}/credits")
def admin_update_user_credits(
    target_user_id: str,
    payload: dict,
    authorization: str | None = Header(default=None),
):
    admin_user = get_current_user_from_auth(authorization)
    if not admin_user.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin access required")

    try:
        amount = int((payload or {}).get("amount", 0))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid amount")

    mode = clean_text((payload or {}).get("mode", "")).lower()

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    if mode not in {"add", "deduct"}:
        raise HTTPException(status_code=400, detail="Invalid mode")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT credits_balance FROM users WHERE id = %s", (target_user_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")

            current_balance = int(row[0] or 0)
            if mode == "deduct":
                new_balance = max(0, current_balance - amount)
            else:
                new_balance = current_balance + amount

            cur.execute(
                """
                UPDATE users
                SET credits_balance = %s
                WHERE id = %s
                RETURNING id, credits_balance
                """,
                (new_balance, target_user_id),
            )
            updated = cur.fetchone()
            conn.commit()

    return {
        "message": "Credits updated",
        "user_id": str(updated[0]),
        "credits_balance": int(updated[1] or 0),
    }

@app.post("/admin/users/{target_user_id}/credits")
def admin_set_user_credits(
    target_user_id: str,
    payload: dict,
    authorization: str | None = Header(default=None),
):
    admin_user = get_current_user_from_auth(authorization)
    if not admin_user.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin access required")

    credits_balance = int((payload or {}).get("credits_balance", 0))
    monthly_search_count = int((payload or {}).get("monthly_search_count", 0))
    monthly_search_limit = int((payload or {}).get("monthly_search_limit", 0))
    reason = clean_text((payload or {}).get("reason", "admin credit adjustment")) or "admin credit adjustment"

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET
                    credits_balance = %s,
                    monthly_search_count = %s,
                    monthly_search_limit = %s
                WHERE id = %s::uuid
                RETURNING id, email, credits_balance, monthly_search_count, monthly_search_limit
                """,
                (credits_balance, monthly_search_count, monthly_search_limit, target_user_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")

            cur.execute(
                """
                INSERT INTO credit_transactions (
                    user_id,
                    transaction_type,
                    credits,
                    balance_after,
                    reason
                )
                VALUES (%s::uuid, %s, %s, %s, %s)
                """,
                (target_user_id, "adjustment", 0, credits_balance, reason),
            )
        conn.commit()

    return {
        "message": "Credits updated",
        "user_id": str(row[0]),
        "email": row[1],
        "credits_balance": int(row[2] or 0),
        "monthly_search_count": int(row[3] or 0),
        "monthly_search_limit": int(row[4] or 0),
    }


@app.post("/admin/users/{target_user_id}/reset-usage")
def admin_reset_user_usage(
    target_user_id: str,
    authorization: str | None = Header(default=None),
):
    admin_user = get_current_user_from_auth(authorization)
    if not admin_user.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin access required")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT plan_code FROM users WHERE id = %s::uuid",
                (target_user_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")

            plan_code = row[0] or ""
            plan = BILLING_PLANS.get(plan_code, BILLING_PLANS["starter"])
            monthly_credits = int(plan.get("monthly_credits", 0))

            cur.execute(
                """
                UPDATE users
                SET
                    credits_balance = %s,
                    monthly_search_count = 0,
                    monthly_search_limit = %s,
                    credits_reset_at = NOW() + INTERVAL '30 days'
                WHERE id = %s::uuid
                RETURNING id, credits_balance, monthly_search_count, monthly_search_limit, credits_reset_at
                """,
                (monthly_credits, monthly_credits, target_user_id),
            )
            updated = cur.fetchone()
        conn.commit()

    return {
        "message": "Usage reset",
        "user_id": str(updated[0]),
        "credits_balance": int(updated[1] or 0),
        "monthly_search_count": int(updated[2] or 0),
        "monthly_search_limit": int(updated[3] or 0),
        "credits_reset_at": updated[4].isoformat() if updated[4] else None,
    }


@app.post("/admin/users/{target_user_id}/superadmin")
def admin_set_superadmin(
    target_user_id: str,
    payload: dict,
    authorization: str | None = Header(default=None),
):
    admin_user = get_current_user_from_auth(authorization)
    if not admin_user.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin access required")

    is_superadmin = bool((payload or {}).get("is_superadmin", False))

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET is_superadmin = %s
                WHERE id = %s::uuid
                RETURNING id, email, is_superadmin
                """,
                (is_superadmin, target_user_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
        conn.commit()

    return {
        "message": "Superadmin updated",
        "user_id": str(row[0]),
        "email": row[1] or "",
        "is_superadmin": bool(row[2]),
    }


@app.get("/admin/plans")
def admin_list_plans(
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT is_superadmin FROM users WHERE id = %s", (str(user["id"]),))
            row = cur.fetchone()
            if not row or not row[0]:
                raise HTTPException(status_code=403, detail="Admin access required")

            cur.execute(
                """
                SELECT code, name, monthly_credits, monthly_search_limit, price_usd, is_active, features
                FROM subscription_plans
                ORDER BY price_usd ASC, name ASC
                """
            )
            plans = cur.fetchall()

    return {
        "plans": [
            {
                "code": code,
                "name": name,
                "monthly_credits": monthly_credits,
                "monthly_search_limit": monthly_search_limit,
                "price_usd": float(price_usd),
                "is_active": is_active,
                "features": features or {},
            }
            for code, name, monthly_credits, monthly_search_limit, price_usd, is_active, features in plans
        ]
    }


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_file_bytes(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def normalize_mapping_value(value):
    if value is None:
        return ""
    value = str(value).strip()
    if not value:
        return ""
    if value.lower().startswith("unnamed:"):
        return ""
    return value

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def clean_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [clean_text(col) if clean_text(col) else f"column_{i + 1}" for i, col in enumerate(df.columns)]
    df = df.fillna("")
    return df.map(clean_text)


def normalize_phone(value: str) -> str:
    value = clean_text(value)
    if not value:
        return ""
    return re.sub(r"[^\d+|]", "", value)


def guess_bedroom_count(value) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""

    patterns = [
        r"(\d+)\s*bed",
        r"(\d+)\s*br",
        r"(\d+)\s*b/r",
        r"studio",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            if pattern == "studio":
                return "studio"
            return match.group(1)

    return ""


def save_upload_to_disk(filename: str, file_bytes: bytes) -> str:
    safe_name = f"{secrets.token_hex(8)}_{os.path.basename(filename)}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return safe_name


def parse_date_or_none(value):
    value = clean_text(value)
    if not value:
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:
        return None


def build_sheet_response(sheet: dict, preview_rows: int = 5) -> dict:
    df = sheet["dataframe"]
    preview = df.head(preview_rows).to_dict(orient="records")
    return {
        "sheet_name": sheet["sheet_name"],
        "sheet_index": sheet["sheet_index"],
        "row_count": len(df.index),
        "column_count": len(df.columns),
        "headers": list(df.columns),
        "preview": preview,
    }


def get_existing_owner_id(cur, tenant_id: str, full_name: str, email: str, phone: str):
    if email:
        cur.execute(
            """
            SELECT id
            FROM owners
            WHERE tenant_id = %s AND lower(coalesce(email, '')) = %s
            LIMIT 1
            """,
            (tenant_id, email.lower()),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    if phone:
        cur.execute(
            """
            SELECT id
            FROM owners
            WHERE tenant_id = %s AND coalesce(phone, '') = %s
            LIMIT 1
            """,
            (tenant_id, phone),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    if full_name:
        cur.execute(
            """
            SELECT id
            FROM owners
            WHERE tenant_id = %s AND lower(coalesce(full_name, '')) = %s
            LIMIT 1
            """,
            (tenant_id, full_name.lower()),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    return None


def upsert_owner(
    cur,
    tenant_id: str,
    owner_full_name: str,
    owner_first_name: str,
    owner_last_name: str,
    owner_email: str,
    owner_phone: str,
    owner_mailing_address: str,
    owner_nationality: str,
    raw_data: dict,
):
    owner_id = get_existing_owner_id(
        cur,
        tenant_id,
        owner_full_name,
        owner_email,
        owner_phone,
    )

    if owner_id:
        cur.execute(
            """
            UPDATE owners
            SET
                full_name = COALESCE(NULLIF(%s, ''), full_name),
                first_name = COALESCE(NULLIF(%s, ''), first_name),
                last_name = COALESCE(NULLIF(%s, ''), last_name),
                email = COALESCE(NULLIF(%s, ''), email),
                phone = COALESCE(NULLIF(%s, ''), phone),
                mailing_address = COALESCE(NULLIF(%s, ''), mailing_address),
                nationality = COALESCE(NULLIF(%s, ''), nationality),
                raw_data = COALESCE(raw_data, '{}'::jsonb) || %s::jsonb,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                owner_full_name,
                owner_first_name,
                owner_last_name,
                owner_email,
                owner_phone,
                owner_mailing_address,
                owner_nationality,
                json.dumps(raw_data),
                owner_id,
            ),
        )
        return owner_id

    cur.execute(
        """
        INSERT INTO owners (
            tenant_id,
            full_name,
            first_name,
            last_name,
            email,
            phone,
            mailing_address,
            nationality,
            raw_data
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            tenant_id,
            owner_full_name,
            owner_first_name,
            owner_last_name,
            owner_email,
            owner_phone,
            owner_mailing_address,
            owner_nationality,
            json.dumps(raw_data),
        ),
    )
    return cur.fetchone()[0]


def get_existing_property_id(
    cur,
    tenant_id: str,
    city: str,
    district: str,
    master_community: str,
    community: str,
    building_name: str,
    villa_name: str,
    unit_number: str,
    plot_number: str,
    p_number: str,
    municipality_number: str,
):
    city = clean_text(city)
    district = clean_text(district)
    master_community = clean_text(master_community)
    community = clean_text(community)
    building_name = clean_text(building_name)
    villa_name = clean_text(villa_name)
    unit_number = clean_text(unit_number)
    plot_number = clean_text(plot_number)
    p_number = clean_text(p_number)
    municipality_number = clean_text(municipality_number)

    # 1) Best match: unit + building + community
    if unit_number and building_name and community:
        cur.execute(
            """
            SELECT id
            FROM properties
            WHERE tenant_id = %s
              AND coalesce(unit_number, '') = %s
              AND coalesce(building_name, '') = %s
              AND coalesce(community, '') = %s
            LIMIT 1
            """,
            (tenant_id, unit_number, building_name, community),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    # 2) Villa-style match
    if villa_name and community:
        cur.execute(
            """
            SELECT id
            FROM properties
            WHERE tenant_id = %s
              AND coalesce(villa_name, '') = %s
              AND coalesce(community, '') = %s
            LIMIT 1
            """,
            (tenant_id, villa_name, community),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    # 3) Plot + municipality + community together only
    if plot_number and municipality_number and community:
        cur.execute(
            """
            SELECT id
            FROM properties
            WHERE tenant_id = %s
              AND coalesce(plot_number, '') = %s
              AND coalesce(municipality_number, '') = %s
              AND coalesce(community, '') = %s
            LIMIT 1
            """,
            (tenant_id, plot_number, municipality_number, community),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    # 4) P-number only if paired with community
    if p_number and community:
        cur.execute(
            """
            SELECT id
            FROM properties
            WHERE tenant_id = %s
              AND coalesce(p_number, '') = %s
              AND coalesce(community, '') = %s
            LIMIT 1
            """,
            (tenant_id, p_number, community),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    # 5) Careful broad fallback only if enough detail exists
    if community and (building_name or villa_name or unit_number):
        cur.execute(
            """
            SELECT id
            FROM properties
            WHERE tenant_id = %s
              AND coalesce(city, '') = %s
              AND coalesce(district, '') = %s
              AND coalesce(master_community, '') = %s
              AND coalesce(community, '') = %s
              AND coalesce(building_name, '') = %s
              AND coalesce(villa_name, '') = %s
              AND coalesce(unit_number, '') = %s
            LIMIT 1
            """,
            (
                tenant_id,
                city,
                district,
                master_community,
                community,
                building_name,
                villa_name,
                unit_number,
            ),
        )
        row = cur.fetchone()
        if row:
            return row[0]

    return None


def upsert_property(
    cur,
    tenant_id: str,
    city: str,
    district: str,
    master_community: str,
    community: str,
    building_name: str,
    villa_name: str,
    property_type: str,
    unit_number: str,
    developer_name: str,
    plot_number: str,
    p_number: str,
    municipality_number: str,
    raw_data: dict,
):
    if not any([
        unit_number,
        building_name,
        villa_name,
        community,
        master_community,
        district,
        city,
        plot_number,
        p_number,
        municipality_number,
    ]):
        return None

    property_id = get_existing_property_id(
        cur,
        tenant_id,
        city,
        district,
        master_community,
        community,
        building_name,
        villa_name,
        unit_number,
        plot_number,
        p_number,
        municipality_number,
    )

    if property_id:
        cur.execute(
            """
            UPDATE properties
            SET
                property_type = COALESCE(NULLIF(%s, ''), property_type),
                developer_name = COALESCE(NULLIF(%s, ''), developer_name),
                city = COALESCE(NULLIF(%s, ''), city),
                district = COALESCE(NULLIF(%s, ''), district),
                master_community = COALESCE(NULLIF(%s, ''), master_community),
                community = COALESCE(NULLIF(%s, ''), community),
                building_name = COALESCE(NULLIF(%s, ''), building_name),
                villa_name = COALESCE(NULLIF(%s, ''), villa_name),
                unit_number = COALESCE(NULLIF(%s, ''), unit_number),
                plot_number = COALESCE(NULLIF(%s, ''), plot_number),
                p_number = COALESCE(NULLIF(%s, ''), p_number),
                municipality_number = COALESCE(NULLIF(%s, ''), municipality_number),
                raw_data = COALESCE(raw_data, '{}'::jsonb) || %s::jsonb,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                property_type,
                developer_name,
                city,
                district,
                master_community,
                community,
                building_name,
                villa_name,
                unit_number,
                plot_number,
                p_number,
                municipality_number,
                json.dumps(raw_data),
                property_id,
            ),
        )
        return property_id

    cur.execute(
        """
        INSERT INTO properties (
            tenant_id,
            city,
            district,
            master_community,
            community,
            building_name,
            villa_name,
            property_type,
            unit_number,
            developer_name,
            plot_number,
            p_number,
            municipality_number,
            raw_data
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            tenant_id,
            city,
            district,
            master_community,
            community,
            building_name,
            villa_name,
            property_type,
            unit_number,
            developer_name,
            plot_number,
            p_number,
            municipality_number,
            json.dumps(raw_data),
        ),
    )
    return cur.fetchone()[0]


def get_current_user_from_auth(authorization: str | None):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing session token")

    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Missing session token")

    session_token = authorization[len(prefix):].strip()
    if not session_token:
        raise HTTPException(status_code=401, detail="Missing session token")

    session_token_hash = hash_session_token(session_token)

    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    u.id,
                    u.full_name,
                    u.email,
                    u.role,
                    u.tenant_id,
                    t.name,
                    COALESCE(u.plan_code, 'starter'),
                    COALESCE(u.credits_balance, 0),
                    COALESCE(u.monthly_search_count, 0),
                    COALESCE(u.monthly_search_limit, 0),
                    u.credits_reset_at,
                    COALESCE(u.billing_status, 'active'),
                    COALESCE(u.is_superadmin, false),
                    COALESCE(sp.features, '{}'::jsonb)
                FROM user_sessions s
                JOIN users u ON u.id = s.user_id
                LEFT JOIN tenants t ON t.id = u.tenant_id
                LEFT JOIN subscription_plans sp ON sp.code = COALESCE(u.plan_code, 'starter')
                WHERE s.session_token_hash = %s
                  AND s.expires_at > NOW()
                ORDER BY s.created_at DESC
                LIMIT 1
                """,
                (session_token_hash,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Session is invalid or expired")

    (
        user_id,
        full_name,
        email,
        role,
        tenant_id,
        tenant_name,
        plan_code,
        credits_balance,
        monthly_search_count,
        monthly_search_limit,
        credits_reset_at,
        billing_status,
        is_superadmin,
        plan_features,
    ) = row

    return {
        "id": str(user_id),
        "full_name": full_name,
        "email": email,
        "role": role,
        "tenant_id": str(tenant_id),
        "tenant": tenant_name,
        "plan_code": plan_code,
        "plan_name": str(plan_code).title() if plan_code else "Starter",
        "credits_balance": credits_balance,
        "monthly_search_count": monthly_search_count,
        "monthly_search_limit": monthly_search_limit,
        "credits_reset_at": credits_reset_at.isoformat() if credits_reset_at else None,
        "billing_status": billing_status,
        "is_superadmin": bool(is_superadmin),
        "plan_features": plan_features or {},
    }


@app.post("/login")
def login(payload: LoginRequest):
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    u.id,
                    u.full_name,
                    u.email,
                    u.password_hash,
                    u.role,
                    u.tenant_id,
                    t.name,
                    COALESCE(u.plan_code, 'starter'),
                    COALESCE(u.credits_balance, 0),
                    COALESCE(u.monthly_search_count, 0),
                    COALESCE(u.monthly_search_limit, 0),
                    u.credits_reset_at,
                    COALESCE(u.billing_status, 'active'),
                    COALESCE(u.is_superadmin, false)
                FROM users u
                LEFT JOIN tenants t ON t.id = u.tenant_id
                WHERE lower(u.email) = lower(%s)
                LIMIT 1
                """,
                (payload.email,),
            )
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=401, detail="Invalid email or password")

            (
                user_id,
                full_name,
                email,
                password_hash,
                role,
                tenant_id,
                tenant_name,
                plan_code,
                credits_balance,
                monthly_search_count,
                monthly_search_limit,
                credits_reset_at,
                billing_status,
                is_superadmin,
            ) = row

            if not pwd_context.verify(payload.password, password_hash):
                raise HTTPException(status_code=401, detail="Invalid email or password")

            reset_monthly_usage_if_needed(cur, str(user_id))

            cur.execute(
                """
                SELECT
                    COALESCE(plan_code, 'starter'),
                    COALESCE(credits_balance, 0),
                    COALESCE(monthly_search_count, 0),
                    COALESCE(monthly_search_limit, 0),
                    credits_reset_at,
                    COALESCE(billing_status, 'active'),
                    COALESCE(is_superadmin, false)
                FROM users
                WHERE id = %s
                """,
                (str(user_id),),
            )
            billing_row = cur.fetchone()
            if billing_row:
                (
                    plan_code,
                    credits_balance,
                    monthly_search_count,
                    monthly_search_limit,
                    credits_reset_at,
                    billing_status,
                    is_superadmin,
                ) = billing_row

            session_token = secrets.token_urlsafe(32)
            session_token_hash = hash_session_token(session_token)

            cur.execute(
                """
                INSERT INTO user_sessions (
                    user_id,
                    session_token_hash,
                    expires_at
                )
                VALUES (%s, %s, NOW() + INTERVAL '30 days')
                """,
                (str(user_id), session_token_hash),
            )

        conn.commit()

    return {
        "message": "Login successful",
        "session_token": session_token,
        "user": {
            "id": str(user_id),
            "full_name": full_name,
            "email": email,
            "role": role,
            "tenant_id": str(tenant_id),
            "tenant": tenant_name,
            "plan_code": plan_code,
            "credits_balance": credits_balance,
            "monthly_search_count": monthly_search_count,
            "monthly_search_limit": monthly_search_limit,
            "credits_reset_at": credits_reset_at.isoformat() if credits_reset_at else None,
            "billing_status": billing_status,
            "is_superadmin": bool(is_superadmin),
        },
    }


@app.get("/me")
def me(
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)

    plan_code = clean_text(user.get("plan_code") or "starter").lower() or "starter"
    plan = BILLING_PLANS.get(plan_code, BILLING_PLANS["starter"])

    return {
        "id": str(user.get("id", "") or ""),
        "full_name": user.get("full_name", "") or "",
        "email": user.get("email", "") or "",
        "role": user.get("role", "") or "",
        "tenant_id": str(user.get("tenant_id", "") or ""),
        "tenant": user.get("tenant", "") or "",
        "plan_code": plan_code,
        "plan_name": plan.get("name"),
        "credits_balance": int(user.get("credits_balance", 0) or 0),
        "monthly_search_count": int(user.get("monthly_search_count", 0) or 0),
        "monthly_search_limit": int(user.get("monthly_search_limit", plan.get("monthly_credits", 0)) or 0),
        "credits_reset_at": user.get("credits_reset_at"),
        "billing_status": user.get("billing_status", "active"),
        "is_superadmin": bool(user.get("is_superadmin", False)),
        "plan_features": plan.get("features", {}) or {},
    }

@app.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    return {
        "message": "File uploaded",
        "filename": file.filename,
        "size_bytes": os.path.getsize(file_path),
        "uploaded_by": user["email"],
    }


@app.post("/profile-upload")
def profile_upload(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)

    file_bytes = file.file.read()
    source_type, file_type, sheets = parse_uploaded_file(file, file_bytes)

    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB limit")

    file_hash = hash_file_bytes(file_bytes)

    existing_file = None

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, original_filename, created_at
                FROM uploaded_files
                WHERE tenant_id = %s
                  AND file_hash = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user["tenant_id"], file_hash),
            )
            existing_file = cur.fetchone()

    stored_filename = save_upload_to_disk(file.filename, file_bytes)

    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO uploaded_files (
                    tenant_id,
                    uploaded_by,
                    original_filename,
                    stored_filename,
                    file_type,
                    file_size_bytes,
                    file_hash,
                    status,
                    sheet_count
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user["tenant_id"],
                    user["id"],
                    file.filename,
                    stored_filename,
                    file_type,
                    len(file_bytes),
                    file_hash,
                    "profiled",
                    len(sheets),
                ),
            )
            uploaded_file_id = cur.fetchone()[0]

            sheet_items = []
            for sheet in sheets:
                df = sheet["dataframe"]
                headers = list(df.columns)

                cur.execute(
                    """
                    INSERT INTO uploaded_file_sheets (
                        uploaded_file_id,
                        sheet_name,
                        sheet_index,
                        row_count,
                        column_count,
                        headers
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        uploaded_file_id,
                        sheet["sheet_name"],
                        sheet["sheet_index"],
                        len(df.index),
                        len(df.columns),
                        json.dumps(headers),
                    ),
                )
                sheet_id = cur.fetchone()[0]

                sheet_items.append(
                    {
                        "sheet_id": str(sheet_id),
                        **build_sheet_response(sheet),
                    }
                )

        conn.commit()

    return {
        "message": "File profiled successfully",
        "uploaded_file_id": str(uploaded_file_id),
        "duplicate_detected": bool(existing_file),
        "duplicate_of_uploaded_file_id": str(existing_file[0]) if existing_file else None,
        "duplicate_filename": existing_file[1] if existing_file else None,
        "duplicate_created_at": existing_file[2].isoformat() if existing_file else None,
        "source_type": source_type,
        "file_type": file_type,
        "sheet_count": len(sheet_items),
        "sheets": sheet_items,
        "system_fields": sorted(list(SYSTEM_FIELDS)),
        "uploaded_by": user["email"],
    }



def save_upload_to_disk(filename: str, file_bytes: bytes) -> str:
    safe_name = f"{secrets.token_hex(8)}_{os.path.basename(filename)}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return safe_name


def parse_date_or_none(value):
    value = clean_text(value)
    if not value:
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:
        return None


def parse_decimal_or_none(value):
    value = clean_text(value).replace(",", "")
    if not value:
        return None
    try:
        return float(value)
    except Exception:
        return None


def build_sheet_response(sheet, preview_rows: int = 5):
    df = sheet["dataframe"]
    return {
        "sheet_name": sheet["sheet_name"],
        "sheet_index": sheet["sheet_index"],
        "row_count": len(df.index),
        "column_count": len(df.columns),
        "headers": list(df.columns),
        "preview": df.head(preview_rows).to_dict(orient="records"),
    }


def find_owner_id(cur, tenant_id, full_name, email, phone, raw_data):
    normalized_email = clean_text(email).lower()
    normalized_phone = clean_text(phone)
    normalized_name = clean_text(full_name).lower()

    owner_id = None

    if normalized_email:
        cur.execute(
            """
            SELECT id
            FROM owners
            WHERE tenant_id = %s AND lower(coalesce(email, '')) = %s
            LIMIT 1
            """,
            (tenant_id, normalized_email),
        )
        row = cur.fetchone()
        if row:
            owner_id = row[0]

    if owner_id is None and normalized_phone:
        cur.execute(
            """
            SELECT id
            FROM owners
            WHERE tenant_id = %s AND coalesce(phone, '') = %s
            LIMIT 1
            """,
            (tenant_id, normalized_phone),
        )
        row = cur.fetchone()
        if row:
            owner_id = row[0]

    if owner_id is None and normalized_name:
        cur.execute(
            """
            SELECT id
            FROM owners
            WHERE tenant_id = %s AND lower(coalesce(full_name, '')) = %s
            LIMIT 1
            """,
            (tenant_id, normalized_name),
        )
        row = cur.fetchone()
        if row:
            owner_id = row[0]

    if owner_id:
        cur.execute(
            """
            UPDATE owners
            SET
                full_name = COALESCE(NULLIF(%s, ''), full_name),
                first_name = COALESCE(NULLIF(%s, ''), first_name),
                last_name = COALESCE(NULLIF(%s, ''), last_name),
                email = COALESCE(NULLIF(%s, ''), email),
                phone = COALESCE(NULLIF(%s, ''), phone),
                mailing_address = COALESCE(NULLIF(%s, ''), mailing_address),
                nationality = COALESCE(NULLIF(%s, ''), nationality),
                raw_data = COALESCE(raw_data, '{}'::jsonb) || %s::jsonb,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                clean_text(raw_data.get("full_name", "")),
                clean_text(raw_data.get("first_name", "")),
                clean_text(raw_data.get("last_name", "")),
                clean_text(raw_data.get("email", "")),
                clean_text(raw_data.get("phone", "")),
                clean_text(raw_data.get("mailing_address", "")),
                clean_text(raw_data.get("nationality", "")),
                json.dumps(raw_data),
                owner_id,
            ),
        )
        return owner_id

    cur.execute(
        """
        INSERT INTO owners (
            tenant_id,
            full_name,
            first_name,
            last_name,
            email,
            phone,
            mailing_address,
            nationality,
            raw_data
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            tenant_id,
            clean_text(raw_data.get("full_name", "")),
            clean_text(raw_data.get("first_name", "")),
            clean_text(raw_data.get("last_name", "")),
            clean_text(raw_data.get("email", "")),
            clean_text(raw_data.get("phone", "")),
            clean_text(raw_data.get("mailing_address", "")),
            clean_text(raw_data.get("nationality", "")),
            json.dumps(raw_data),
        ),
    )
    return cur.fetchone()[0]


def find_property_id(cur, tenant_id, city, district, master_community, community, building_name, villa_name, unit_number, property_type, developer_name, raw_data):
    if not any([city, district, master_community, community, building_name, villa_name, unit_number]):
        return None

    cur.execute(
        """
        SELECT id
        FROM properties
        WHERE tenant_id = %s
          AND coalesce(city, '') = %s
          AND coalesce(district, '') = %s
          AND coalesce(master_community, '') = %s
          AND coalesce(community, '') = %s
          AND coalesce(building_name, '') = %s
          AND coalesce(villa_name, '') = %s
          AND coalesce(unit_number, '') = %s
        LIMIT 1
        """,
        (
            tenant_id,
            clean_text(city),
            clean_text(district),
            clean_text(master_community),
            clean_text(community),
            clean_text(building_name),
            clean_text(villa_name),
            clean_text(unit_number),
        ),
    )
    row = cur.fetchone()

    if row:
        property_id = row[0]
        cur.execute(
            """
            UPDATE properties
            SET
                property_type = COALESCE(NULLIF(%s, ''), property_type),
                developer_name = COALESCE(NULLIF(%s, ''), developer_name),
                raw_data = COALESCE(raw_data, '{}'::jsonb) || %s::jsonb,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                clean_text(property_type),
                clean_text(developer_name),
                json.dumps(raw_data),
                property_id,
            ),
        )
        return property_id

    cur.execute(
        """
        INSERT INTO properties (
            tenant_id,
            city,
            district,
            master_community,
            community,
            building_name,
            villa_name,
            property_type,
            unit_number,
            developer_name,
            raw_data
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            tenant_id,
            clean_text(city),
            clean_text(district),
            clean_text(master_community),
            clean_text(community),
            clean_text(building_name),
            clean_text(villa_name),
            clean_text(property_type),
            clean_text(unit_number),
            clean_text(developer_name),
            json.dumps(raw_data),
        ),
    )
    return cur.fetchone()[0]


@app.post("/finalize-import")
def finalize_import(
    payload: FinalizeImportRequest,
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)

    required_missing = []

    for sheet in payload.sheets:
        mappings = {k: normalize_mapping_value(v) for k, v in sheet.mappings.items()}
        mapped_targets = {v for v in mappings.values() if v}

        for required_field in REQUIRED_SYSTEM_FIELDS:
            if required_field not in mapped_targets:
                required_missing.append(required_field)

    if required_missing:
        missing_unique = sorted(set(required_missing))
        raise HTTPException(
            status_code=400,
            detail=f"Missing required mappings: {', '.join(missing_unique)}"
        )

    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    uploaded_file_id = payload.uploaded_file_id
    requested_sheet_ids = {item.sheet_id for item in payload.sheets}

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, stored_filename, original_filename
                FROM uploaded_files
                WHERE id = %s AND tenant_id = %s
                LIMIT 1
                """,
                (uploaded_file_id, user["tenant_id"]),
            )
            upload_row = cur.fetchone()

            if not upload_row:
                raise HTTPException(status_code=404, detail="Uploaded file not found")

            _, stored_filename, original_filename = upload_row
            file_path = os.path.join(UPLOAD_DIR, stored_filename or "")

            if not stored_filename or not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Stored upload file not found on server")

            cur.execute(
                """
                SELECT id, sheet_name, sheet_index
                FROM uploaded_file_sheets
                WHERE uploaded_file_id = %s
                ORDER BY sheet_index
                """,
                (uploaded_file_id,),
            )
            db_sheets = cur.fetchall()

            db_sheet_map = {
                str(row[0]): {
                    "id": row[0],
                    "sheet_name": row[1],
                    "sheet_index": row[2],
                }
                for row in db_sheets
            }

            for sheet_id in requested_sheet_ids:
                if sheet_id not in db_sheet_map:
                    raise HTTPException(status_code=400, detail=f"Invalid sheet_id: {sheet_id}")

            with open(file_path, "rb") as f:
                file_bytes = f.read()

            class LocalUploadFile:
                def __init__(self, filename: str):
                    self.filename = filename

            source_type, file_type, sheets = parse_uploaded_file(
                LocalUploadFile(original_filename),
                file_bytes,
            )

            parsed_sheet_map = {
                sheet["sheet_index"]: sheet
                for sheet in sheets
            }

            for sheet_item in payload.sheets:
                for source_column, target_field in sheet_item.mappings.items():
                    if target_field not in SYSTEM_FIELDS:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid target field: {target_field}",
                        )

                    if not clean_text(source_column):
                        raise HTTPException(
                            status_code=400,
                            detail="Source column name cannot be empty",
                        )

            cur.execute(
                "DELETE FROM uploaded_file_mappings WHERE uploaded_file_id = %s",
                (uploaded_file_id,),
            )

            records_created = 0
            owners_linked = 0
            transactions_created = 0

            for sheet_item in payload.sheets:
                db_sheet = db_sheet_map[sheet_item.sheet_id]
                sheet_index = db_sheet["sheet_index"]
                parsed_sheet = parsed_sheet_map.get(sheet_index)

                if not parsed_sheet:
                    continue

                df = parsed_sheet["dataframe"]

                for source_column, target_field in sheet_item.mappings.items():
                    cur.execute(
                        """
                        INSERT INTO uploaded_file_mappings (
                            uploaded_file_id,
                            uploaded_file_sheet_id,
                            source_column_name,
                            target_field,
                            is_required
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            uploaded_file_id,
                            db_sheet["id"],
                            source_column,
                            target_field,
                            target_field in {"owner_full_name", "property_unit_number"},
                        ),
                    )

                for _, row in df.iterrows():
                    raw_row = {k: clean_text(v) for k, v in row.to_dict().items()}
                    mappings = sheet_item.mappings

                    def mapped(system_field: str) -> str:
                        source_col = None
                        for column_name, target_name in mappings.items():
                            if target_name == system_field:
                                source_col = column_name
                                break
                        if not source_col:
                            return ""
                        return clean_text(raw_row.get(source_col, ""))

                    owner_full_name = mapped("owner_full_name")
                    owner_first_name = mapped("owner_first_name")
                    owner_last_name = mapped("owner_last_name")
                    owner_email = mapped("owner_email")
                    owner_phone = normalize_phone(mapped("owner_phone"))
                    owner_mailing_address = mapped("owner_mailing_address")
                    owner_nationality = mapped("owner_nationality")
                    property_city = mapped("property_city")
                    property_district = mapped("property_district")
                    property_master_community = mapped("property_master_community")
                    property_community = mapped("property_community")
                    property_building_name = mapped("property_building_name")
                    property_villa_name = mapped("property_villa_name")
                    property_unit_number = mapped("property_unit_number")
                    property_type = mapped("property_type")
                    property_developer_name = mapped("property_developer_name")
                    property_plot_number = mapped("property_plot_number")
                    property_p_number = mapped("property_p_number")
                    property_municipality_number = mapped("property_municipality_number")
                    transaction_type = mapped("transaction_type")
                    transaction_date = parse_date_or_none(mapped("transaction_date"))
                    transaction_price_raw = mapped("transaction_price")
                    transaction_currency = mapped("transaction_currency") or "AED"
                    transaction_notes = mapped("transaction_notes")

                    if not any(
                        [
                            owner_full_name,
                            owner_email,
                            owner_phone,
                            property_unit_number,
                            property_building_name,
                            property_villa_name,
                            property_community,
                            property_master_community,
                            property_district,
                            property_city,
                            property_plot_number,
                            property_p_number,
                            property_municipality_number,
                        ]
                    ):

                        continue

                    owner_id = upsert_owner(
                        cur,
                        user["tenant_id"],
                        owner_full_name,
                        owner_first_name,
                        owner_last_name,
                        owner_email,
                        owner_phone,
                        owner_mailing_address,
                        owner_nationality,
                        raw_row,
                    )

                    property_id = upsert_property(
                        cur,
                        user["tenant_id"],
                        property_city,
                        property_district,
                        property_master_community,
                        property_community,
                        property_building_name,
                        property_villa_name,
                        property_type,
                        property_unit_number,
                        property_developer_name,
                        property_plot_number,
                        property_p_number,
                        property_municipality_number,
                        raw_row,
                    )

                    if property_id and owner_id:
                        cur.execute(
                            """
                            SELECT id
                            FROM property_owner_links
                            WHERE tenant_id = %s AND property_id = %s AND owner_id = %s
                            LIMIT 1
                            """,
                            (user["tenant_id"], property_id, owner_id),
                        )
                        existing_link = cur.fetchone()

                        if not existing_link:
                            cur.execute(
                                """
                                INSERT INTO property_owner_links (
                                    tenant_id,
                                    property_id,
                                    owner_id,
                                    ownership_type,
                                    is_primary_owner,
                                    match_confidence,
                                    source_upload_id
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    user["tenant_id"],
                                    property_id,
                                    owner_id,
                                    "owner",
                                    True,
                                    100.00 if (owner_email or owner_phone) else 70.00,
                                    uploaded_file_id,
                                ),
                            )
                            owners_linked += 1

                    transaction_price = None
                    if transaction_price_raw:
                        cleaned_price = re.sub(r"[^0-9.]", "", transaction_price_raw)
                        if cleaned_price:
                            try:
                                transaction_price = float(cleaned_price)
                            except ValueError:
                                transaction_price = None

                    if property_id and (
                        transaction_type or transaction_date or transaction_price is not None or transaction_notes
                    ):
                        cur.execute(
                            """
                            SELECT id
                            FROM property_transactions
                            WHERE tenant_id = %s
                              AND property_id = %s
                              AND COALESCE(owner_id::text, '') = COALESCE(%s::text, '')
                              AND COALESCE(transaction_type, '') = %s
                              AND transaction_date IS NOT DISTINCT FROM %s
                              AND price IS NOT DISTINCT FROM %s
                              AND COALESCE(currency, '') = %s
                              AND COALESCE(notes, '') = %s
                            LIMIT 1
                            """,
                            (
                                user["tenant_id"],
                                property_id,
                                owner_id,
                                transaction_type or "",
                                transaction_date,
                                transaction_price,
                                transaction_currency or "",
                                transaction_notes or "",
                            ),
                        )
                        existing_transaction = cur.fetchone()

                        if not existing_transaction:
                            cur.execute(
                                """
                                INSERT INTO property_transactions (
                                    tenant_id,
                                    property_id,
                                    owner_id,
                                    transaction_type,
                                    transaction_date,
                                    price,
                                    currency,
                                    notes,
                                    source_upload_id,
                                    raw_data
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    user["tenant_id"],
                                    property_id,
                                    owner_id,
                                    transaction_type,
                                    transaction_date,
                                    transaction_price,
                                    transaction_currency,
                                    transaction_notes,
                                    uploaded_file_id,
                                    json.dumps(raw_row),
                                ),
                            )
                            transactions_created += 1

                    if owner_id or property_id:
                        records_created += 1

            cur.execute(
                """
                UPDATE uploaded_files
                SET status = %s
                WHERE id = %s
                """,
                ("imported", uploaded_file_id),
            )

        conn.commit()

    return {
        "message": "Import finalized successfully",
        "uploaded_file_id": uploaded_file_id,
        "records_processed": records_created,
        "owners_linked": owners_linked,
        "transactions_created": transactions_created,
        "sheet_count": len(payload.sheets),
        "uploaded_by": user["email"],
    }



@app.get("/owners")
def list_owners(
    authorization: str | None = Header(default=None),
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
):
    user = get_current_user_from_auth(authorization)

    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    sql = """
        SELECT
            id,
            full_name,
            first_name,
            last_name,
            email,
            phone,
            mailing_address,
            nationality,
            whatsapp_active,
            linkedin_url,
            facebook_url,
            instagram_url,
            snapchat_url,
            profile_image_url,
            raw_data,
            created_at,
            updated_at
        FROM owners
        WHERE tenant_id = %s
    """
    params = [user["tenant_id"]]

    q = clean_text(q)
    if q:
        sql += """
            AND (
                coalesce(full_name, '') ILIKE %s
                OR coalesce(email, '') ILIKE %s
                OR coalesce(phone, '') ILIKE %s
                OR coalesce(nationality, '') ILIKE %s
            )
        """
        like_q = f"%{q}%"
        params.extend([like_q, like_q, like_q, like_q])

    sql += " ORDER BY updated_at DESC, created_at DESC LIMIT %s"
    params.append(limit)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        (
            owner_id,
            full_name,
            first_name,
            last_name,
            email,
            phone,
            mailing_address,
            nationality,
            whatsapp_active,
            linkedin_url,
            facebook_url,
            instagram_url,
            snapchat_url,
            profile_image_url,
            raw_data,
            created_at,
            updated_at,
        ) = row

        results.append(
            {
                "id": str(owner_id),
                "full_name": full_name,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "mailing_address": mailing_address,
                "nationality": nationality,
                "whatsapp_active": whatsapp_active,
                "linkedin_url": linkedin_url,
                "facebook_url": facebook_url,
                "instagram_url": instagram_url,
                "snapchat_url": snapchat_url,
                "profile_image_url": profile_image_url,
                "raw_data": raw_data,
                "created_at": created_at.isoformat() if created_at else None,
                "updated_at": updated_at.isoformat() if updated_at else None,
            }
        )

    return {
        "count": len(results),
        "results": results,
    }


@app.get("/properties")
def list_properties(
    authorization: str | None = Header(default=None),
    q: str = Query(default=""),
    city: str = Query(default=""),
    district: str = Query(default=""),
    master_community: str = Query(default=""),
    community: str = Query(default=""),
    building_name: str = Query(default=""),
    unit_number: str = Query(default=""),
    property_type: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
):
    user = get_current_user_from_auth(authorization)

    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    sql = """
        SELECT
            id,
            city,
            district,
            master_community,
            community,
            building_name,
            villa_name,
            property_type,
            unit_number,
            developer_name,
            plot_number,
            p_number,
            municipality_number,
            raw_data,
            created_at,
            updated_at
        FROM properties
        WHERE tenant_id = %s
    """
    params = [user["tenant_id"]]

    def add_filter(field_name: str, value: str):
        nonlocal sql, params
        value = clean_text(value)
        if value:
            sql += f" AND coalesce({field_name}, '') ILIKE %s"
            params.append(f"%{value}%")

    q = clean_text(q)
    if q:
        sql += """
            AND (
                coalesce(city, '') ILIKE %s
                OR coalesce(district, '') ILIKE %s
                OR coalesce(master_community, '') ILIKE %s
                OR coalesce(community, '') ILIKE %s
                OR coalesce(building_name, '') ILIKE %s
                OR coalesce(villa_name, '') ILIKE %s
                OR coalesce(unit_number, '') ILIKE %s
                OR coalesce(property_type, '') ILIKE %s
                OR coalesce(plot_number, '') ILIKE %s
                OR coalesce(p_number, '') ILIKE %s
                OR coalesce(municipality_number, '') ILIKE %s
            )
        """
        like_q = f"%{q}%"
        params.extend([like_q] * 11)

    add_filter("city", city)
    add_filter("district", district)
    add_filter("master_community", master_community)
    add_filter("community", community)
    add_filter("building_name", building_name)
    add_filter("unit_number", unit_number)
    add_filter("property_type", property_type)

    sql += " ORDER BY updated_at DESC, created_at DESC LIMIT %s"
    params.append(limit)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        (
            property_id,
            city_val,
            district_val,
            master_community_val,
            community_val,
            building_name_val,
            villa_name_val,
            property_type_val,
            unit_number_val,
            developer_name_val,
            plot_number_val,
            p_number_val,
            municipality_number_val,
            raw_data_val,
            created_at_val,
            updated_at_val,
        ) = row

        results.append(
            {
                "id": str(property_id),
                "city": city_val,
                "district": district_val,
                "master_community": master_community_val,
                "community": community_val,
                "building_name": building_name_val,
                "villa_name": villa_name_val,
                "property_type": property_type_val,
                "unit_number": unit_number_val,
                "developer_name": developer_name_val,
                "plot_number": plot_number_val,
                "p_number": p_number_val,
                "municipality_number": municipality_number_val,
                "raw_data": raw_data_val,
                "created_at": created_at_val.isoformat() if created_at_val else None,
                "updated_at": updated_at_val.isoformat() if updated_at_val else None,
            }
        )

    return {
        "count": len(results),
        "results": results,
    }


@app.get("/transactions")
def list_transactions(
    authorization: str | None = Header(default=None),
    q: str = Query(default=""),
    transaction_type: str = Query(default=""),
    currency: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
):
    user = get_current_user_from_auth(authorization)

    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    sql = """
        SELECT
            pt.id,
            pt.property_id,
            pt.owner_id,
            pt.transaction_type,
            pt.transaction_date,
            pt.price,
            pt.currency,
            pt.notes,
            pt.source_upload_id,
            pt.raw_data,
            pt.created_at
        FROM property_transactions pt
        LEFT JOIN properties p ON p.id = pt.property_id
        LEFT JOIN owners o ON o.id = pt.owner_id
        WHERE pt.tenant_id = %s
    """
    params = [user["tenant_id"]]

    q = clean_text(q)
    if q:
        sql += """
            AND (
                COALESCE(pt.transaction_type, '') ILIKE %s
                OR COALESCE(pt.currency, '') ILIKE %s
                OR COALESCE(pt.notes, '') ILIKE %s
                OR COALESCE(p.city, '') ILIKE %s
                OR COALESCE(p.district, '') ILIKE %s
                OR COALESCE(p.master_community, '') ILIKE %s
                OR COALESCE(p.community, '') ILIKE %s
                OR COALESCE(p.building_name, '') ILIKE %s
                OR COALESCE(p.villa_name, '') ILIKE %s
                OR COALESCE(p.unit_number, '') ILIKE %s
                OR COALESCE(p.plot_number, '') ILIKE %s
                OR COALESCE(p.p_number, '') ILIKE %s
                OR COALESCE(p.municipality_number, '') ILIKE %s
                OR COALESCE(o.full_name, '') ILIKE %s
                OR COALESCE(o.phone, '') ILIKE %s
                OR COALESCE(o.nationality, '') ILIKE %s
            )
        """
        like_q = f"%{q}%"
        params.extend([like_q] * 16)

    transaction_type = clean_text(transaction_type)
    if transaction_type:
        sql += " AND COALESCE(pt.transaction_type, '') ILIKE %s"
        params.append(f"%{transaction_type}%")

    currency = clean_text(currency)
    if currency:
        sql += " AND COALESCE(pt.currency, '') ILIKE %s"
        params.append(f"%{currency}%")

    sql += " ORDER BY pt.transaction_date DESC NULLS LAST, pt.created_at DESC LIMIT %s"
    params.append(limit)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        (
            transaction_id,
            property_id,
            owner_id,
            transaction_type_val,
            transaction_date_val,
            price_val,
            currency_val,
            notes_val,
            source_upload_id,
            raw_data_val,
            created_at_val,
        ) = row

        results.append(
            {
                "id": str(transaction_id),
                "property_id": str(property_id) if property_id else None,
                "owner_id": str(owner_id) if owner_id else None,
                "transaction_type": transaction_type_val,
                "transaction_date": transaction_date_val.isoformat() if transaction_date_val else None,
                "price": float(price_val) if price_val is not None else None,
                "currency": currency_val,
                "notes": notes_val,
                "source_upload_id": str(source_upload_id) if source_upload_id else None,
                "raw_data": raw_data_val,
                "created_at": created_at_val.isoformat() if created_at_val else None,
            }
        )

    return {"count": len(results), "results": results}





@app.post("/import-upload")
def import_upload(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)

    file_bytes = file.file.read()
    source_type, file_type, sheets = parse_uploaded_file(file, file_bytes)

    records_to_insert = []

    if source_type == "type_a":
        if len(sheets) < 2:
            raise HTTPException(status_code=400, detail="Type A file must contain at least 2 sheets")

        sheet1 = sheets[0]["dataframe"]
        sheet2 = sheets[1]["dataframe"]

        owner_map = build_type_a_owner_map(sheet1)

        merged_rows = []
        for _, row in sheet2.iterrows():
            raw_row = row.to_dict()
            p_number = normalize_p_number(
                first_non_empty(raw_row, ["P-NUMBER", "P NUMBER", "Plot Number", "Plot No", sheet2.columns[0]])
            )
            owner_row = owner_map.get(p_number, {})
            merged = {}
            merged.update(owner_row)
            merged.update(raw_row)
            merged_rows.append(merged)

        if merged_rows:
            merged_df = clean_dataframe(pd.DataFrame(merged_rows))
            column_map = build_column_map(merged_df)

            for _, row in merged_df.iterrows():
                record = normalize_record(row.to_dict(), column_map, sheets[1]["sheet_name"])
                if any(
                    [
                        record["owner_name"],
                        record["email"],
                        record["phone"],
                        record["project_name"],
                        record["master_community"],
                        record["unit_number"],
                        record["plot_number"],
                    ]
                ):
                    records_to_insert.append(record)

    else:
        for sheet in sheets:
            df = sheet["dataframe"]
            column_map = build_column_map(df)

            for _, row in df.iterrows():
                record = normalize_record(row.to_dict(), column_map, sheet["sheet_name"])
                if any(
                    [
                        record["owner_name"],
                        record["email"],
                        record["phone"],
                        record["project_name"],
                        record["master_community"],
                        record["unit_number"],
                        record["plot_number"],
                    ]
                ):
                    records_to_insert.append(record)

    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO import_batches (
                    tenant_id,
                    uploaded_by,
                    original_filename,
                    source_type,
                    file_type,
                    sheet_count
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user["tenant_id"],
                    user["id"],
                    file.filename,
                    source_type,
                    file_type,
                    len(sheets),
                ),
            )
            import_batch_id = cur.fetchone()[0]

            for record in records_to_insert:
                cur.execute(
                    """
                    INSERT INTO property_records (
                        tenant_id,
                        import_batch_id,
                        owner_name,
                        owner_name_ar,
                        email,
                        phone,
                        district,
                        master_community,
                        project_name,
                        sub_community,
                        property_type,
                        bedroom_count,
                        unit_number,
                        building_name,
                        plot_number,
                        developer_name,
                        source_sheet,
                        raw_data
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        user["tenant_id"],
                        import_batch_id,
                        record["owner_name"],
                        record["owner_name_ar"],
                        record["email"],
                        record["phone"],
                        record["district"],
                        record["master_community"],
                        record["project_name"],
                        record["sub_community"],
                        record["property_type"],
                        record["bedroom_count"],
                        record["unit_number"],
                        record["building_name"],
                        record["plot_number"],
                        record["developer_name"],
                        record["source_sheet"],
                        json.dumps(record["raw_data"]),
                    ),
                )

        conn.commit()

    return {
        "message": "Import completed",
        "filename": file.filename,
        "source_type": source_type,
        "file_type": file_type,
        "sheet_count": len(sheets),
        "records_imported": len(records_to_insert),
        "uploaded_by": user["email"],
    }




def parse_nl_search_query(q: str) -> dict:
    q_clean = clean_text(q)
    q_lower = q_clean.lower()

    filters = {
        "owner_name": "",
        "phone": "",
        "unit_number": "",
        "master_community": "",
        "project_name": "",
        "property_type": "",
        "district": "",
        "limit": 20,
    }

    phone_match = re.search(r'(?<!\d)(\+?\d[\d\-\s]{7,}\d)', q_clean)
    if phone_match:
        filters["phone"] = re.sub(r"[^0-9+]", "", phone_match.group(1))

    unit_match = re.search(r'\bunit\s*[:#-]?\s*([a-zA-Z0-9\-\/]+)', q_clean, flags=re.I)
    if unit_match:
        filters["unit_number"] = clean_text(unit_match.group(1))

    owned_by_match = re.search(r'(?:owned by|owner is|by)\s+([a-zA-Z][a-zA-Z\s\.\'-]{2,})', q_clean, flags=re.I)
    if owned_by_match:
        filters["owner_name"] = clean_text(owned_by_match.group(1))

    in_match = re.search(r'(?:in|at)\s+([a-zA-Z0-9\s\-\&]+)', q_clean, flags=re.I)
    if in_match:
        place = clean_text(in_match.group(1))
        if place and not filters["project_name"]:
            filters["project_name"] = place

    property_keywords = {
        "villa": "Villa",
        "villas": "Villa",
        "apartment": "Apartment",
        "apartments": "Apartment",
        "flat": "Apartment",
        "flats": "Apartment",
        "commercial": "Commercial",
        "office": "Office",
        "offices": "Office",
        "building": "Building",
        "residential": "Residential",
        "plot": "Plot",
    }

    for k, v in property_keywords.items():
        if re.search(rf'\b{re.escape(k)}\b', q_lower):
            filters["property_type"] = v
            break

    known_projects = [
        "ARABIAN RANCHES - PALMA COMMUNITY",
        "Arabian Ranches III - JOY",
        "Arabian Ranches III - SUN",
        "Arabian Ranches lll - Caya",
        "Arabian Ranches lll",
        "558 Villa",
        "Wadi Al Safa 5",
        "Wadi Al Safa 7",
    ]

    for proj in known_projects:
        if proj.lower() in q_lower:
            if proj.lower().startswith("wadi al safa"):
                filters["district"] = proj
            elif proj == "558 Villa":
                filters["master_community"] = proj
            else:
                filters["project_name"] = proj

    if not filters["owner_name"]:
        m = re.search(r'\b(lara|ahmed|hafiz|delaram|lijesh|abdul rahim|sundoo)\b', q_lower)
        if m:
            filters["owner_name"] = clean_text(m.group(1))

    return filters

@app.get("/search-ai")
def search_ai(
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)

    filters = parse_nl_search_query(q) or {}

    owner_name_cleaned = clean_text(filters.get("owner_name", ""))
    if owner_name_cleaned:
        owner_name_cleaned = re.split(r'\b(?:in|at|with|phone|email|unit|plot)\b', owner_name_cleaned, maxsplit=1, flags=re.I)[0].strip(" ,-")
        filters["owner_name"] = owner_name_cleaned

    q_norm = clean_text(q).lower()

    if not filters.get("phone"):
        m = re.search(r"(971\d{9}|05\d{8}|\d{7,15})", q_norm)
        if m:
            filters["phone"] = m.group(1)

    if not filters.get("unit_number"):
        m = re.search(r"(?:unit|plot|villa)\s+([a-z0-9\-/]+)", q_norm)
        if m:
            filters["unit_number"] = m.group(1).upper()

    if not filters.get("owner_name"):
        m = re.search(r"\b(?:lara|ahmed|hafiz|delaram|lijesh|abdul rahim|sundoo)\b", q_norm)
        if m:
            filters["owner_name"] = clean_text(m.group(0))

    if not filters.get("project_name") and "palma" in q_norm:
        filters["project_name"] = "PALMA"
        filters["sub_community"] = "PALMA"

    if not filters.get("property_type"):
        for pt in ["villa", "apartment", "commercial", "office", "retail", "plot", "warehouse"]:
            if pt in q_norm:
                filters["property_type"] = pt.title()
                break

    results_response = search_properties(
        authorization=f"Bearer {authorization.split(' ', 1)[1]}" if authorization and authorization.startswith("Bearer ") else authorization,
        owner_name=filters.get("owner_name", ""),
        email=filters.get("email", ""),
        phone=filters.get("phone", ""),
        district=filters.get("district", ""),
        master_community=filters.get("master_community", ""),
        project_name=filters.get("project_name", ""),
        sub_community=filters.get("sub_community", ""),
        bedroom_count=filters.get("bedroom_count", ""),
        unit_number=filters.get("unit_number", ""),
        property_type=filters.get("property_type", ""),
        limit=limit,
        offset=offset,
        suppress_billing=True,
    )

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            billing_meta = consume_credits_and_log(
                cur,
                user=user,
                endpoint="/search-ai",
                query_text=q,
                owner_name=filters.get("owner_name", ""),
                phone=filters.get("phone", ""),
                email=filters.get("email", ""),
                unit_number=filters.get("unit_number", ""),
                project_name=filters.get("project_name", ""),
                property_type=filters.get("property_type", ""),
                result_count=len(results_response.get("results", [])),
                metadata={
                    "district": filters.get("district", ""),
                    "master_community": filters.get("master_community", ""),
                    "sub_community": filters.get("sub_community", ""),
                    "ai_query": q,
                },
            )
        conn.commit()

    results_response["credits_used"] = billing_meta["credits_used"]
    results_response["credits_balance"] = billing_meta["credits_balance"]
    results_response["area_tier"] = billing_meta["area_tier"]
    results_response["matched_area_key"] = billing_meta["matched_area_key"]
    results_response["billing_source"] = "/search-ai"
    return results_response

@app.get("/search")
def search_properties(
    authorization: str | None = Header(default=None),
    owner_name: str = Query(default=""),
    email: str = Query(default=""),
    phone: str = Query(default=""),
    district: str = Query(default=""),
    master_community: str = Query(default=""),
    project_name: str = Query(default=""),
    sub_community: str = Query(default=""),
    bedroom_count: str = Query(default=""),
    unit_number: str = Query(default=""),
    property_type: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    suppress_billing: bool = False,
):
    user = get_current_user_from_auth(authorization)

    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    owner_name_clean = clean_text(owner_name)
    email_clean = clean_text(email)
    phone_clean = clean_text(phone)
    district_clean = clean_text(district)
    master_community_clean = clean_text(master_community)
    project_name_clean = clean_text(project_name)
    sub_community_clean = clean_text(sub_community)
    bedroom_count_clean = clean_text(bedroom_count)
    unit_number_clean = clean_text(unit_number)

    sql = """
        SELECT
            o.id AS owner_id,
            pol.id AS link_id,
            o.full_name AS owner_name,
            '' AS owner_name_ar,
            o.email,
            o.phone,
            coalesce(p.district, '') AS district,
            coalesce(p.master_community, '') AS master_community,
            coalesce(p.community, '') AS project_name,
            coalesce(p.community, '') AS sub_community,
            coalesce(p.property_type, '') AS property_type,
            '' AS bedroom_count,
            coalesce(p.unit_number, '') AS unit_number,
            coalesce(p.building_name, '') AS building_name,
            coalesce(p.plot_number, '') AS plot_number,
            coalesce(p.developer_name, '') AS developer_name,
            '' AS source_sheet,
            coalesce(o.raw_data, '{}'::jsonb) AS raw_data,
            pol.created_at,
            CASE
                WHEN %s <> '' THEN GREATEST(
                    similarity(coalesce(o.full_name, ''), %s),
                    similarity(coalesce(p.unit_number, ''), %s),
                    similarity(coalesce(p.community, ''), %s),
                    similarity(coalesce(p.master_community, ''), %s),
                    similarity(coalesce(o.phone, ''), %s)
                )
                ELSE 0
            END AS rank_score
        FROM property_owner_links pol
        JOIN owners o ON o.id = pol.owner_id
        JOIN properties p ON p.id = pol.property_id
        WHERE pol.tenant_id = %s
    """
    params = [
        owner_name_clean,
        owner_name_clean,
        owner_name_clean,
        owner_name_clean,
        owner_name_clean,
        owner_name_clean,
        user["tenant_id"],
    ]

    def add_filter(expr: str, value: str):
        nonlocal sql, params
        if value:
            sql += f" AND {expr} ILIKE %s"
            params.append(f"%{value}%")

    add_filter("coalesce(o.full_name, '')", owner_name_clean)
    add_filter("coalesce(o.email, '')", email_clean)
    add_filter("coalesce(o.phone, '')", phone_clean)
    add_filter("coalesce(p.district, '')", district_clean)
    add_filter("coalesce(p.master_community, '')", master_community_clean)
    add_filter("coalesce(p.community, '')", project_name_clean)
    add_filter("coalesce(p.community, '')", sub_community_clean)
    add_filter("coalesce(p.unit_number, '')", unit_number_clean)

    if bedroom_count_clean:
        add_filter("coalesce(o.raw_data->>'ROOMS DESCRIPTION', '')", bedroom_count_clean)

    sql += """
        ORDER BY
            rank_score DESC,
            pol.created_at DESC,
            o.updated_at DESC NULLS LAST,
            o.created_at DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    count_sql = """
        SELECT count(*)
        FROM property_owner_links pol
        JOIN owners o ON o.id = pol.owner_id
        JOIN properties p ON p.id = pol.property_id
        WHERE pol.tenant_id = %s
    """
    count_params = [user["tenant_id"]]

    def add_count_filter(expr: str, value: str):
        nonlocal count_sql, count_params
        if value:
            count_sql += f" AND {expr} ILIKE %s"
            count_params.append(f"%{value}%")

    add_count_filter("coalesce(o.full_name, '')", owner_name_clean)
    add_count_filter("coalesce(o.email, '')", email_clean)
    add_count_filter("coalesce(o.phone, '')", phone_clean)
    add_count_filter("coalesce(p.district, '')", district_clean)
    add_count_filter("coalesce(p.master_community, '')", master_community_clean)
    add_count_filter("coalesce(p.community, '')", project_name_clean)
    add_count_filter("coalesce(p.community, '')", sub_community_clean)
    add_count_filter("coalesce(p.unit_number, '')", unit_number_clean)

    if bedroom_count_clean:
        add_count_filter("coalesce(o.raw_data->>'ROOMS DESCRIPTION', '')", bedroom_count_clean)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(count_sql, count_params)
            total_count = cur.fetchone()[0]

            cur.execute(sql, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        (
            owner_id_val,
            record_id,
            owner_name_val,
            owner_name_ar_val,
            email_val,
            phone_val,
            district_val,
            master_community_val,
            project_name_val,
            sub_community_val,
            property_type_val,
            bedroom_count_val,
            unit_number_val,
            building_name_val,
            plot_number_val,
            developer_name_val,
            source_sheet_val,
            raw_data_val,
            created_at_val,
            rank_score_val,
        ) = row

        results.append(
            {
                "id": str(owner_id_val),
                "owner_id": str(owner_id_val),
                "link_id": str(record_id),
                "owner_name": owner_name_val,
                "owner_name_ar": owner_name_ar_val,
                "email": email_val,
                "phone": phone_val,
                "district": district_val,
                "master_community": master_community_val,
                "project_name": project_name_val,
                "sub_community": sub_community_val,
                "property_type": property_type_val,
                "bedroom_count": bedroom_count_val,
                "unit_number": unit_number_val,
                "building_name": building_name_val,
                "plot_number": plot_number_val,
                "developer_name": developer_name_val,
                "source_sheet": source_sheet_val,
                "raw_data": raw_data_val,
                "created_at": created_at_val.isoformat() if created_at_val else None,
                "rank_score": float(rank_score_val or 0),
            }
        )

    if suppress_billing:
        return {
            "count": len(results),
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "credits_used": 0,
            "credits_balance": user.get("credits_balance", 0),
            "area_tier": "standard",
            "matched_area_key": "",
            "results": results,
        }

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            billing_meta = consume_credits_and_log(
                cur,
                user=user,
                endpoint="/search",
                query_text=" ".join([
                    clean_text(owner_name),
                    clean_text(email),
                    clean_text(phone),
                    clean_text(district),
                    clean_text(master_community),
                    clean_text(project_name),
                    clean_text(sub_community),
                    clean_text(bedroom_count),
                    clean_text(unit_number),
                    clean_text(property_type),
                ]).strip(),
                owner_name=owner_name,
                phone=phone,
                email=email,
                unit_number=unit_number,
                project_name=project_name,
                property_type=property_type,
                result_count=len(results),
                metadata={
                    "district": district,
                    "master_community": master_community,
                    "sub_community": sub_community,
                    "limit": limit,
                    "offset": offset,
                    "total_count": total_count,
                },
            )
        conn.commit()

    return {
        "count": len(results),
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "credits_used": billing_meta["credits_used"],
        "credits_balance": billing_meta["credits_balance"],
        "area_tier": billing_meta["area_tier"],
        "matched_area_key": billing_meta["matched_area_key"],
        "results": results,
    }




@app.get("/export")
def export_data(
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)

    plan_code = (user.get("plan_code") or "").lower()
    is_superadmin = bool(user.get("is_superadmin", False))

    export_enabled = is_superadmin or plan_code in {"pro", "enterprise"}

    if not export_enabled:
        raise HTTPException(status_code=403, detail="Export not enabled for your plan")

    return {
        "ok": True,
        "message": "Export endpoint is enabled",
        "user_email": user.get("email", ""),
        "plan_code": user.get("plan_code", ""),
        "export_enabled": True,
    }

@app.get("/owners/{owner_id}")

def get_owner_detail(
    owner_id: str,
    authorization: str | None = Header(default=None),
):
    user = get_current_user_from_auth(authorization)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    full_name,
                    first_name,
                    last_name,
                    email,
                    phone,
                    mailing_address,
                    nationality,
                    whatsapp_active,
                    linkedin_url,
                    facebook_url,
                    instagram_url,
                    snapchat_url,
                    profile_image_url,
                    raw_data,
                    created_at,
                    updated_at
                FROM owners
                WHERE id = %s
                LIMIT 1
                """,
                (owner_id,),
            )
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Owner not found")

            owner = {
                "id": str(row[0]),
                "full_name": row[1],
                "first_name": row[2] or "",
                "last_name": row[3] or "",
                "email": row[4] or "",
                "phone": row[5] or "",
                "mailing_address": row[6] or "",
                "nationality": row[7] or "",
                "whatsapp_active": row[8],
                "linkedin_url": row[9],
                "facebook_url": row[10],
                "instagram_url": row[11],
                "snapchat_url": row[12],
                "profile_image_url": row[13],
                "raw_data": row[14] or {},
                "created_at": row[15].isoformat() if row[15] else None,
                "updated_at": row[16].isoformat() if row[16] else None,
            }

            cur.execute(
                """
                SELECT
                    pol.id,
                    p.id,
                    '' AS city,
                    COALESCE(p.district, '') AS district,
                    COALESCE(p.master_community, '') AS master_community,
                    COALESCE(p.community, '') AS community,
                    COALESCE(p.building_name, '') AS building_name,
                    '' AS villa_name,
                    COALESCE(p.unit_number, '') AS unit_number,
                    COALESCE(p.property_type, '') AS property_type,
                    COALESCE(p.developer_name, '') AS developer_name,
                    COALESCE(p.plot_number, '') AS plot_number,
                    '' AS p_number,
                    '' AS municipality_number,
                    COALESCE(p.raw_data, '{}'::jsonb) AS raw_data,
                    COALESCE(pol.ownership_type, 'owner') AS ownership_type,
                    COALESCE(pol.is_primary_owner, false) AS is_primary_owner,
                    COALESCE(pol.match_confidence, 0) AS match_confidence,
                    pol.created_at AS linked_at
                FROM property_owner_links pol
                JOIN properties p ON p.id = pol.property_id
                WHERE pol.owner_id = %s
                ORDER BY pol.created_at DESC
                """,
                (owner_id,),
            )
            rows = cur.fetchall()

            properties = []
            for r in rows:
                properties.append({
                    "link_id": str(r[0]),
                    "property_id": str(r[1]),
                    "city": r[2] or "",
                    "district": r[3] or "",
                    "master_community": r[4] or "",
                    "community": r[5] or "",
                    "building_name": r[6] or "",
                    "villa_name": r[7] or "",
                    "unit_number": r[8] or "",
                    "property_type": r[9] or "",
                    "developer_name": r[10] or "",
                    "plot_number": r[11] or "",
                    "p_number": r[12] or "",
                    "municipality_number": r[13] or "",
                    "raw_data": r[14] or {},
                    "ownership_type": r[15] or "",
                    "is_primary_owner": bool(r[16]),
                    "match_confidence": float(r[17]) if r[17] is not None else 0.0,
                    "linked_at": r[18].isoformat() if r[18] else None,
                })

            billing_meta = consume_credits_and_log(
                cur,
                user=user,
                endpoint=f"/owners/{owner_id}",
                query_text=owner.get("full_name", ""),
                owner_name=owner.get("full_name", ""),
                phone=owner.get("phone", ""),
                email=owner.get("email", ""),
                unit_number=properties[0].get("unit_number", "") if properties else "",
                project_name=properties[0].get("community", "") if properties else "",
                property_type=properties[0].get("property_type", "") if properties else "",
                result_count=len(properties),
                metadata={
                    "owner_id": owner_id,
                    "properties_count": len(properties),
                },
            )
        conn.commit()

    return {
        "owner": owner,
        "properties_count": len(properties),
        "credits_used": billing_meta["credits_used"],
        "credits_balance": billing_meta["credits_balance"],
        "area_tier": billing_meta["area_tier"],
        "matched_area_key": billing_meta["matched_area_key"],
        "billing_source": f"/owners/{owner_id}",
        "properties": properties,
    }

app.get("/search-ai")
