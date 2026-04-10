BEGIN;

CREATE TABLE IF NOT EXISTS subscription_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    monthly_credits INTEGER NOT NULL DEFAULT 0,
    monthly_search_limit INTEGER NOT NULL DEFAULT 0,
    price_usd NUMERIC(12,2) NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    features JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS plan_code TEXT,
    ADD COLUMN IF NOT EXISTS credits_balance INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS monthly_search_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS monthly_search_limit INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS credits_reset_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS billing_status TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS is_superadmin BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS credit_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    transaction_type TEXT NOT NULL,
    credits INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS search_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    endpoint TEXT NOT NULL,
    query_text TEXT NOT NULL DEFAULT '',
    owner_name TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    unit_number TEXT NOT NULL DEFAULT '',
    project_name TEXT NOT NULL DEFAULT '',
    property_type TEXT NOT NULL DEFAULT '',
    credits_used INTEGER NOT NULL DEFAULT 0,
    result_count INTEGER NOT NULL DEFAULT 0,
    area_tier TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'success',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS premium_areas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    area_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    area_tier TEXT NOT NULL DEFAULT 'premium',
    credit_cost INTEGER NOT NULL DEFAULT 5,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_created
    ON credit_transactions (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_usage_logs_user_created
    ON search_usage_logs (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_usage_logs_tenant_created
    ON search_usage_logs (tenant_id, created_at DESC);

INSERT INTO subscription_plans (code, name, monthly_credits, monthly_search_limit, price_usd, is_active, features)
VALUES
    ('starter', 'Starter', 200, 200, 49.00, true, '{"ai_search": true, "owner_detail": true, "export": false}'::jsonb),
    ('growth', 'Growth', 1000, 1000, 149.00, true, '{"ai_search": true, "owner_detail": true, "export": true}'::jsonb),
    ('pro', 'Pro', 5000, 5000, 499.00, true, '{"ai_search": true, "owner_detail": true, "export": true, "api": true}'::jsonb)
ON CONFLICT (code) DO NOTHING;

INSERT INTO premium_areas (area_key, display_name, area_tier, credit_cost, is_active)
VALUES
    ('palm jumeirah', 'Palm Jumeirah', 'premium', 5, true),
    ('downtown dubai', 'Downtown Dubai', 'premium', 4, true),
    ('emirates hills', 'Emirates Hills', 'premium', 5, true),
    ('dubai marina', 'Dubai Marina', 'premium', 3, true),
    ('jumeirah bay', 'Jumeirah Bay', 'premium', 5, true),
    ('district one', 'District One', 'premium', 4, true)
ON CONFLICT (area_key) DO NOTHING;

UPDATE users
SET
    plan_code = COALESCE(plan_code, 'pro'),
    credits_balance = CASE WHEN credits_balance = 0 THEN 5000 ELSE credits_balance END,
    monthly_search_limit = CASE WHEN monthly_search_limit = 0 THEN 5000 ELSE monthly_search_limit END,
    credits_reset_at = COALESCE(credits_reset_at, NOW() + INTERVAL '30 days'),
    is_superadmin = CASE
        WHEN email = 'admin@truproplookup.trucrm.io' THEN true
        ELSE is_superadmin
    END
WHERE true;

COMMIT;
