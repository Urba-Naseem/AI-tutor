-- 1. Enable pgcrypto for SHA-256 calculation inside PostgreSQL
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2. Create the immutable activity_events table (AIT-43)
CREATE TABLE IF NOT EXISTS activity_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    user_id UUID NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    prev_hash VARCHAR(64) NOT NULL,
    hash VARCHAR(64) NOT NULL
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_activity_events_user_id ON activity_events(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_events_event_type ON activity_events(event_type);

-- 3. AIT-44: Trigger 1 — Prevent UPDATE and DELETE operations
CREATE OR REPLACE FUNCTION prevent_audit_alteration()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Action Denied: activity_events table is append-only. UPDATE and DELETE operations are strictly forbidden.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_append_only_audit
BEFORE UPDATE OR DELETE ON activity_events
FOR EACH ROW
EXECUTE FUNCTION prevent_audit_alteration();

-- 4. AIT-44: Revoke modification privileges from public/application roles
REVOKE UPDATE, DELETE ON activity_events FROM PUBLIC;

-- 5. Trigger 2 — Automatic Cryptographic Hash Chain Generator
CREATE OR REPLACE FUNCTION generate_audit_hash_chain()
RETURNS TRIGGER AS $$
DECLARE
    last_hash VARCHAR(64);
    payload TEXT;
BEGIN
    -- Acquire advisory lock to guarantee sequence order under concurrent requests
    PERFORM pg_advisory_xact_lock(424242);

    -- Get the hash of the latest event
    SELECT hash INTO last_hash
    FROM activity_events
    ORDER BY id DESC
    LIMIT 1;

    -- Set genesis hash for the first record in the table
    IF last_hash IS NULL THEN
        last_hash := '0000000000000000000000000000000000000000000000000000000000000000';
    END IF;

    -- Assign prev_hash and timestamp
    NEW.prev_hash := last_hash;
    IF NEW.created_at IS NULL THEN
        NEW.created_at := NOW();
    END IF;

    -- Construct hash payload: prev_hash|event_type|user_id|created_at|details
    payload := NEW.prev_hash || '|' ||
               NEW.event_type || '|' ||
               COALESCE(NEW.user_id::text, '') || '|' ||
               NEW.created_at::text || '|' ||
               COALESCE(NEW.details::text, '{}');

    -- Compute SHA-256 hash
    NEW.hash := encode(digest(payload, 'sha256'), 'hex');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER compute_event_hash_chain
BEFORE INSERT ON activity_events
FOR EACH ROW
EXECUTE FUNCTION generate_audit_hash_chain();