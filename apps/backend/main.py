import os
import re
import json
import secrets
import hashlib
from io import BytesIO

from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Query
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
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [clean_text(col) if clean_text(col) else f"column_{i + 1}" for i, col in enumerate(df.columns)]
    df = df.fillna("")
    return df.applymap(clean_text)


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
            cur.execute(
                """
                SELECT
                    u.id,
                    u.full_name,
                    u.email,
                    u.role,
                    u.status,
                    u.tenant_id,
                    t.name
                FROM active_sessions s
                JOIN users u ON u.id = s.user_id
                JOIN tenants t ON t.id = u.tenant_id
                WHERE s.session_token_hash = %s
                  AND s.is_revoked = FALSE
                LIMIT 1
                """,
                (token_hash,),
            )
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=401, detail="Session is invalid or expired")

            user_id, full_name, email, role, status, tenant_id, tenant_name = row

            if status != "active":
                raise HTTPException(status_code=403, detail="User is not active")

            cur.execute(
                """
                UPDATE active_sessions
                SET last_seen_at = NOW()
                WHERE session_token_hash = %s
                """,
                (token_hash,),
            )
        conn.commit()

    return {
        "id": str(user_id),
        "full_name": full_name,
        "email": email,
        "role": role,
        "tenant_id": str(tenant_id),
        "tenant": tenant_name,
    }


def detect_column_type(column_name: str) -> str:
    name = clean_text(column_name).lower()

    if not name:
        return "unknown"

    if "p-number" in name or "p number" in name:
        return "plot_number"

    if "owner" in name and "arabic" in name:
        return "owner_name_ar"
    if "owner" in name and "name" in name:
        return "owner_name"
    if name in {"owner", "owner name"}:
        return "owner_name"

    if ("office" in name or "company" in name or "agency" in name or "brokerage" in name) and "arabic" in name:
        return "company_name_ar"
    if "office" in name or "company" in name or "agency" in name or "brokerage" in name:
        return "company_name"

    if "email" in name:
        return "email"

    if "phone" in name or "mobile" in name or "tel" in name or "contact number" in name:
        return "phone"

    if "district" in name or name == "area":
        return "district"

    if "master community" in name:
        return "master_community"

    if "sub community" in name:
        return "sub_community"

    if "community" in name:
        return "master_community"

    if "project" in name or "cluster" in name:
        return "project_name"

    if "property type" in name or "unit type" in name:
        return "property_type"

    if "bedroom" in name or name == "b/r" or name == "br":
        return "bedroom_count"

    if "unit number" in name or "unit no" in name or "apartment number" in name or "villa number" in name:
        return "unit_number"

    if "building name" in name or name == "tower" or name == "building":
        return "building_name"

    if "plot number" in name or "plot no" in name:
        return "plot_number"

    if "developer" in name:
        return "developer_name"

    if "name arabic" in name:
        return "owner_name_ar"

    if "name english" in name or name == "name":
        return "owner_name"

    return "unknown"


def build_column_map(df: pd.DataFrame) -> dict[str, str]:
    return {col: detect_column_type(col) for col in df.columns}


def find_first_value(row: dict, column_map: dict, target_type: str) -> str:
    for col, mapped in column_map.items():
        if mapped == target_type:
            value = clean_text(row.get(col, ""))
            if value:
                return value
    return ""


def first_non_empty(row_dict: dict, keys: list[str]) -> str:
    for key in keys:
        value = row_dict.get(key)
        value = clean_text(value)
        if value:
            return value
    return ""


def normalize_p_number(value) -> str:
    return clean_text(value).upper()


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

    if not owner_name:
        owner_name = first_non_empty(
            row,
            ["Name English", "Owner Name", "OWNER NAME", "Name", "Customer Name", "Client Name"],
        )

    if not owner_name_ar:
        owner_name_ar = first_non_empty(
            row,
            ["Name Arabic", "Owner Name Arabic", "OWNER NAME ARABIC"],
        )

    if not email:
        email = first_non_empty(row, ["Email", "EMAIL", "E-mail"])

    if not phone:
        phone = first_non_empty(row, ["Phone", "PHONE", "Phone Number", "Mobile", "Mobile Number", "Tel"])

    if not district:
        district = first_non_empty(row, ["District", "DISTRICT", "Area"])

    if not master_community:
        master_community = first_non_empty(row, ["Master Community", "MASTER COMMUNITY", "Community"])

    if not project_name:
        project_name = first_non_empty(row, ["Project", "PROJECT", "Project Name", "Building", "Cluster"])

    if not sub_community:
        sub_community = first_non_empty(row, ["Sub Community", "SUB COMMUNITY", "Cluster", "Phase"])

    if not property_type:
        property_type = first_non_empty(row, ["Property Type", "PROPERTY TYPE", "Type", "Unit Type"])

    if not bedroom_count:
        bedroom_count = first_non_empty(row, ["Bedrooms", "BEDROOMS", "Bedroom", "B/R"])

    if not unit_number:
        unit_number = first_non_empty(
            row,
            ["Unit Number", "UNIT NUMBER", "Unit No", "Apartment Number", "Villa Number"],
        )

    if not building_name:
        building_name = first_non_empty(row, ["Building Name", "BUILDING NAME", "Tower", "Building"])

    if not plot_number:
        plot_number = first_non_empty(row, ["Plot Number", "PLOT NUMBER", "Plot No", "P-NUMBER"])

    if not developer_name:
        developer_name = first_non_empty(row, ["Developer", "Developer Name", "DEVELOPER"])

    if not bedroom_count:
        for value in row.values():
            guessed = guess_bedroom_count(value)
            if guessed:
                bedroom_count = guessed
                break

    return {
        "owner_name": owner_name,
        "owner_name_ar": owner_name_ar,
        "email": email,
        "phone": normalize_phone(phone),
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
        "raw_data": row,
    }


def profile_dataframe(df: pd.DataFrame, sheet_name: str) -> dict:
    df = clean_dataframe(df)
    column_map = build_column_map(df)
    preview = df.head(5).to_dict(orient="records")

    return {
        "sheet_name": sheet_name,
        "row_count": int(df.shape[0]),
        "column_count": int(df.shape[1]),
        "columns": list(df.columns),
        "column_types": column_map,
        "preview": preview,
    }


def parse_uploaded_file(file: UploadFile, file_bytes: bytes) -> tuple[str, str, list[dict]]:
    filename = clean_text(file.filename).lower()

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(BytesIO(file_bytes), dtype=str, keep_default_na=False)
            df = clean_dataframe(df)
            return "type_b", "csv", [{"sheet_name": "Sheet1", "dataframe": df}]

        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            excel_file = pd.ExcelFile(BytesIO(file_bytes))
            sheet_names = excel_file.sheet_names
            sheets = []

            for sheet_name in sheet_names:
                df = excel_file.parse(sheet_name, dtype=str).fillna("")
                df = clean_dataframe(df)
                sheets.append({"sheet_name": sheet_name, "dataframe": df})

            source_type = "type_a" if len(sheet_names) >= 2 else "type_b"
            return source_type, "excel", sheets

        raise HTTPException(status_code=400, detail="Unsupported file type")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")


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
            cur.execute(
                """
                SELECT u.id, u.full_name, u.email, u.password_hash, u.role, u.status, t.id, t.name
                FROM users u
                JOIN tenants t ON t.id = u.tenant_id
                WHERE LOWER(u.email) = LOWER(%s)
                LIMIT 1
                """,
                (payload.email,),
            )
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=401, detail="Invalid email or password")

            user_id, full_name, email, password_hash, role, status, tenant_id, tenant_name = row

            if status != "active":
                raise HTTPException(status_code=403, detail="User is not active")

            if not pwd_context.verify(payload.password, password_hash):
                raise HTTPException(status_code=401, detail="Invalid email or password")

            cur.execute(
                """
                UPDATE active_sessions
                SET is_revoked = TRUE, revoked_at = NOW()
                WHERE user_id = %s AND is_revoked = FALSE
                """,
                (user_id,),
            )

            raw_token = secrets.token_urlsafe(32)
            token_hash = hash_session_token(raw_token)

            cur.execute(
                """
                INSERT INTO active_sessions (user_id, session_token_hash, is_revoked)
                VALUES (%s, %s, FALSE)
                """,
                (user_id, token_hash),
            )

        conn.commit()

    return {
        "message": "Login successful",
        "session_token": raw_token,
        "user": {
            "id": str(user_id),
            "full_name": full_name,
            "email": email,
            "role": role,
            "tenant_id": str(tenant_id),
            "tenant": tenant_name,
        },
    }


@app.get("/me")
def me(authorization: str | None = Header(default=None)):
    user = get_current_user_from_auth(authorization)
    return {"message": "Session valid", "user": user}


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

    profiled_sheets = [
        profile_dataframe(sheet["dataframe"], sheet["sheet_name"])
        for sheet in sheets
    ]

    return {
        "source_type": source_type,
        "file_type": file_type,
        "sheet_count": len(profiled_sheets),
        "sheets": profiled_sheets,
        "uploaded_by": user["email"],
    }


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
    limit: int = Query(default=50, ge=1, le=200),
):
    user = get_current_user_from_auth(authorization)

    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing")

    sql = """
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
            raw_data,
            created_at
        FROM property_records
        WHERE tenant_id = %s
    """
    params = [user["tenant_id"]]

    def add_filter(field_name: str, value: str):
        nonlocal sql, params
        value = clean_text(value)
        if value:
            sql += f" AND {field_name} ILIKE %s"
            params.append(f"%{value}%")

    add_filter("owner_name", owner_name)
    add_filter("email", email)
    add_filter("phone", phone)
    add_filter("district", district)
    add_filter("master_community", master_community)
    add_filter("project_name", project_name)
    add_filter("sub_community", sub_community)
    add_filter("bedroom_count", bedroom_count)
    add_filter("unit_number", unit_number)

    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        (
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
        ) = row

        results.append(
            {
                "id": str(record_id),
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
            }
        )

    return {
        "count": len(results),
        "results": results,
    }
