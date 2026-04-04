CREATE TABLE IF NOT EXISTS import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    source_type TEXT,
    file_type TEXT NOT NULL,
    sheet_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS property_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    import_batch_id UUID NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,

    owner_name TEXT,
    owner_name_ar TEXT,
    email TEXT,
    phone TEXT,

    district TEXT,
    master_community TEXT,
    project_name TEXT,
    sub_community TEXT,

    property_type TEXT,
    bedroom_count TEXT,
    unit_number TEXT,
    building_name TEXT,
    plot_number TEXT,

    developer_name TEXT,
    source_sheet TEXT,

    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_property_records_tenant_id
    ON property_records (tenant_id);

CREATE INDEX IF NOT EXISTS idx_property_records_owner_name
    ON property_records (owner_name);

CREATE INDEX IF NOT EXISTS idx_property_records_email
    ON property_records (email);

CREATE INDEX IF NOT EXISTS idx_property_records_phone
    ON property_records (phone);

CREATE INDEX IF NOT EXISTS idx_property_records_master_community
    ON property_records (master_community);

CREATE INDEX IF NOT EXISTS idx_property_records_project_name
    ON property_records (project_name);

CREATE INDEX IF NOT EXISTS idx_property_records_sub_community
    ON property_records (sub_community);

CREATE INDEX IF NOT EXISTS idx_property_records_bedroom_count
    ON property_records (bedroom_count);

CREATE INDEX IF NOT EXISTS idx_property_records_unit_number
    ON property_records (unit_number);
