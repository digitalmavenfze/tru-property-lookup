import os
import re
import json
import secrets
import hashlib
from io import BytesIO

from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import psycopg
from dotenv import load_dotenv
import pandas as pd

load_dotenv("/app/.env")

app = FastAPI(title="Tru Property Lookup API")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DATABASE_URL = os.getenv("DATABASE_URL")
UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [clean_text(col) for col in df.columns]
    df = df.fillna("")
    for col in df.columns:
        df[col] = df[col].astype(str).map(clean_text)
    return df


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
                    t.id,
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

            user_id, full_name, email, role, status, tenant_id, tenant_name = row

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
        "tenant_id": str(tenant_id),
        "tenant": tenant_name
    }


def detect_column_type(column_name: str) -> str:
    name = clean_text(column_name).lower()

    if ("owner" in name and "name" in name) or name in {"owner", "owner name", "name of owner"}:
        return "owner_name"
    if ("owner" in name and ("arabic" in name or "ar" in name)) or "owner name arabic" in name:
        return "owner_name_ar"
    if "email" in name:
        return "email"
    if "phone" in name or "mobile" in name or "tel" in name or "contact" in name:
        return "phone"
    if "district" in name or "area" in name:
        return "district"
    if "master community" in name:
        return "master_community"
    if "project" in name:
        return "project_name"
    if "community" in name or "cluster" in name or "sub community" in name or "sub_community" in name:
        return "sub_community"
    if "property type" in name or "unit type" in name:
        return "property_type"
    if "bedroom" in name or name == "bed" or name == "beds" or name == "br":
        return "bedroom_count"
    if "unit number" in name or name == "unit" or "apartment" in name or "villa number" in name:
        return "unit_number"
    if "building" in name or "tower" in name:
        return "building_name"
    if "plot" in name:
        return "plot_number"
    if "developer" in name:
        return "developer_name"

    return "unknown"


def guess_bedroom_count(value: str) -> str:
    text = clean_text(value).lower()
    if not text:
        return ""

    m = re.search(r'(\d+)\s*(bed|beds|br|bedroom|bedrooms)', text)
    if m:
        return m.group(1)

    if text == "studio":
        return "studio"

    return ""


def build_column_map(df: pd.DataFrame) -> dict[str, str]:
    return {col: detect_column_type(col) for col in df.columns}


def find_first_value(row: dict, column_map: dict, target_type: str) -> str:
    for col, mapped in column_map.items():
        if mapped == target_type:
            value = clean_text(row.get(col, ""))
            if value:
                return value
    return ""
def normalize_p_number(value) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def build_type_a_owner_map(sheet1: pd.DataFrame) -> dict:
    owner_map = {}

    if sheet1.empty:
        return owner_map

    first_col = sheet1.columns[0]

    for _, row in sheet1.iterrows():
        p_number = normalize_p_number(row.get(first_col))
        if p_number:
            owner_map[p_number] = row.to_dict()

    return owner_map
sheet2 = clean_dataframe(excel_file.parse(sheet_names[1], dtype=str).fillna(""))

owner_map = build_type_a_owner_map(sheet1)

for _, row in sheet2.iterrows():
    raw_row = row.to_dict()

    p_number = normalize_p_number(
        row.get("P-NUMBER") or row.get("P_NUMBER") or row.get("PNUMBER")
    )

    owner_row = owner_map.get(p_number, {})

    owner_name = first_non_empty(owner_row, [
        "Owner Name", "OWNER NAME", "Name", "Customer Name", "Owner"
    ])

    owner_name_ar = first_non_empty(owner_row, [
        "Owner Name Arabic", "OWNER NAME ARABIC", "Name Arabic"
    ])

    email = first_non_empty(owner_row, [
        "Email", "EMAIL", "Email Address"
    ])

    phone = first_non_empty(owner_row, [
        "Phone", "PHONE", "Mobile", "Contact Number"
    ])

    district = first_non_empty(raw_row, [
        "District", "DISTRICT", "Area"
    ])

    master_community = first_non_empty(raw_row, [
        "Master Community", "MASTER COMMUNITY", "Community"
    ])

    project_name = first_non_empty(raw_row, [
        "Project", "PROJECT", "Project Name", "Building", "Cluster"
    ])

    sub_community = first_non_empty(raw_row, [
        "Sub Community", "SUB COMMUNITY", "Cluster", "Phase"
    ])


def normalize_record(row: dict, column_map: dict, sheet_name: str) -> dict:
    owner_name = find_first_value(row, column_map, "owner_name")
    owner_name_ar = find_first_value(row, column_map, "owner_name_ar")
    email = find_first_value(row, column_map, "email")
    phone = find_first_value(row, column_map, "phone")
    district = find_first_value(row, column_map, "district")
    master_community = find_first_value(row, column_map, "master_community")
    project_name = find_first_value(row, column_map, "project_name")
    sub_community = find_first_value(row, column_map, "sub_community")
    property_type = find_first_value(row, column_map, "property_type")
    bedroom_count = find_first_value(row, column_map, "bedroom_count")
    unit_number = find_first_value(row, column_map, "unit_number")
    building_name = find_first_value(row, column_map, "building_name")
    plot_number = find_first_value(row, column_map, "plot_number")
    developer_name = find_first_value(row, column_map, "developer_name")

    if not bedroom_count:
        for value in row.values():
            guessed = guess_bedroom_count(value)
            if guessed:
                bedroom_count = guessed
                break

    if not master_community and district:
        master_community = district

    if not sub_community and project_name:
        sub_community = project_name

    return {
        "owner_name": owner_name,
        "owner_name_ar": owner_name_ar,
        "email": email,
        "phone": phone,
        "district": district,
        "master_community": master_community,
        "project_name": project_name,
        "sub_community": sub_community,
        "property_type": property_type,
        "bedroom_count": bedroom_count,
        "unit_number": unit_number,
        "building_name": building_name,
        "plot_number": plot_number,
        "developer_name": developer_name,
        "source_sheet": sheet_name,
        "raw_data": row
    }


def read_excel_sheets(file_bytes: bytes) -> dict[str, pd.DataFrame]:
    excel_file = pd.ExcelFile(BytesIO(file_bytes))
    sheets = {}
    for sheet_name in excel_file.sheet_names:
        df = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name, dtype=str).fillna("")
        sheets[sheet_name] = clean_dataframe(df)
    return sheets


def detect_source_type(filename: str, sheets: dict[str, pd.DataFrame]) -> str:
    if filename.lower().endswith(".csv"):
        return "type_b"
    if len(sheets) >= 2:
        return "type_a"
    return "type_b"


@app.get("/")
def root():
    return {"app": "Tru Property Lookup API", "status": "ok"}


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
    return {"message": "Session valid", "user": user}


@app.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None)
):
    user = get_current_user_from_auth(authorization)

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    return {
        "message": "File uploaded",
        "filename": file.filename,
        "size_bytes": os.path.getsize(file_path),
        "uploaded_by": user["email"]
    }


@app.post("/profile-upload")
def profile_upload(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None)
):
    user = get_current_user_from_auth(authorization)
    file_bytes = file.file.read()
    filename = file.filename or "uploaded_file"

    try:
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(BytesIO(file_bytes), dtype=str, keep_default_na=False)
            df = clean_dataframe(df)

            return {
                "source_type": "type_b",
                "file_type": "csv",
                "sheet_count": 1,
                "sheets": [
                    {
                        "sheet_name": "Sheet1",
                        "row_count": int(df.shape[0]),
                        "column_count": int(df.shape[1]),
                        "columns": list(df.columns),
                        "column_types": build_column_map(df),
                        "preview": df.head(5).to_dict(orient="records")
                    }
                ],
                "uploaded_by": user["email"]
            }

        if filename.lower().endswith((".xlsx", ".xls")):
            sheets = read_excel_sheets(file_bytes)
            result_sheets = []

            for sheet_name, df in sheets.items():
                result_sheets.append({
                    "sheet_name": sheet_name,
                    "row_count": int(df.shape[0]),
                    "column_count": int(df.shape[1]),
                    "columns": list(df.columns),
                    "column_types": build_column_map(df),
                    "preview": df.head(5).to_dict(orient="records")
                })

            return {
                "source_type": detect_source_type(filename, sheets),
                "file_type": "excel",
                "sheet_count": len(sheets),
                "sheets": result_sheets,
                "uploaded_by": user["email"]
            }

        raise HTTPException(status_code=400, detail="Unsupported file type")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")


@app.post("/import-upload")
def import_upload(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None)
):
    user = get_current_user_from_auth(authorization)
    file_bytes = file.file.read()
    filename = file.filename or "uploaded_file"

    try:
        if filename.lower().endswith(".csv"):
            sheets = {
                "Sheet1": clean_dataframe(
                    pd.read_csv(BytesIO(file_bytes), dtype=str, keep_default_na=False)
                )
            }
            file_type = "csv"
        elif filename.lower().endswith((".xlsx", ".xls")):
            sheets = read_excel_sheets(file_bytes)
            file_type = "excel"
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        source_type = detect_source_type(filename, sheets)
        inserted_count = 0

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
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
                """, (
                    user["tenant_id"],
                    user["id"],
                    filename,
                    source_type,
                    file_type,
                    len(sheets)
                ))
                import_batch_id = cur.fetchone()[0]

                for sheet_name, df in sheets.items():
                    column_map = build_column_map(df)

                    for row in df.to_dict(orient="records"):
                        normalized = normalize_record(row, column_map, sheet_name)

                        if not any([
                            normalized["owner_name"],
                            normalized["owner_name_ar"],
                            normalized["email"],
                            normalized["phone"],
                            normalized["district"],
                            normalized["master_community"],
                            normalized["project_name"],
                            normalized["sub_community"],
                            normalized["unit_number"],
                            normalized["building_name"],
                            normalized["plot_number"]
                        ]):
                            continue

                        cur.execute("""
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
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                            )
                        """, (
                            user["tenant_id"],
                            str(import_batch_id),
                            normalized["owner_name"],
                            normalized["owner_name_ar"],
                            normalized["email"],
                            normalized["phone"],
                            normalized["district"],
                            normalized["master_community"],
                            normalized["project_name"],
                            normalized["sub_community"],
                            normalized["property_type"],
                            normalized["bedroom_count"],
                            normalized["unit_number"],
                            normalized["building_name"],
                            normalized["plot_number"],
                            normalized["developer_name"],
                            normalized["source_sheet"],
                            json.dumps(normalized["raw_data"], ensure_ascii=False)
                        ))
                        inserted_count += 1

            conn.commit()

        return {
            "message": "Import completed",
            "filename": filename,
            "source_type": source_type,
            "file_type": file_type,
            "sheet_count": len(sheets),
            "records_imported": inserted_count,
            "uploaded_by": user["email"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import file: {str(e)}")


@app.get("/search")
def search_records(
    community: str | None = None,
    project: str | None = None,
    bedrooms: str | None = None,
    unit_number: str | None = None,
    owner_name: str | None = None,
    authorization: str | None = Header(default=None)
):
    user = get_current_user_from_auth(authorization)

    where_parts = ["tenant_id = %s"]
    params = [user["tenant_id"]]

    if community:
        where_parts.append("""
            (
                COALESCE(master_community, '') ILIKE %s OR
                COALESCE(district, '') ILIKE %s OR
                COALESCE(sub_community, '') ILIKE %s
            )
        """)
        like_value = f"%{community}%"
        params.extend([like_value, like_value, like_value])

    if project:
        where_parts.append("""
            (
                COALESCE(project_name, '') ILIKE %s OR
                COALESCE(sub_community, '') ILIKE %s OR
                COALESCE(building_name, '') ILIKE %s
            )
        """)
        like_value = f"%{project}%"
        params.extend([like_value, like_value, like_value])

    if bedrooms:
        where_parts.append("COALESCE(bedroom_count, '') ILIKE %s")
        params.append(f"%{bedrooms}%")

    if unit_number:
        where_parts.append("COALESCE(unit_number, '') ILIKE %s")
        params.append(f"%{unit_number}%")

    if owner_name:
        where_parts.append("""
            (
                COALESCE(owner_name, '') ILIKE %s OR
                COALESCE(owner_name_ar, '') ILIKE %s
            )
        """)
        like_value = f"%{owner_name}%"
        params.extend([like_value, like_value])

    query = f"""
        SELECT
            id,
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
        FROM property_records
        WHERE {' AND '.join(where_parts)}
        ORDER BY created_at DESC
        LIMIT 100
    """

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        results.append({
            "id": str(row[0]),
            "owner_name": row[1],
            "owner_name_ar": row[2],
            "email": row[3],
            "phone": row[4],
            "district": row[5],
            "master_community": row[6],
            "project_name": row[7],
            "sub_community": row[8],
            "property_type": row[9],
            "bedroom_count": row[10],
            "unit_number": row[11],
            "building_name": row[12],
            "plot_number": row[13],
            "developer_name": row[14],
            "source_sheet": row[15],
            "raw_data": row[16]
        })

    return {
        "count": len(results),
        "results": results
    }
