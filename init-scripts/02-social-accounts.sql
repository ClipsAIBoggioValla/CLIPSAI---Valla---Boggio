-- =============================================================================
-- clipsai — DDL SocialAccount (Issue #22)
-- Cuentas OAuth vinculadas por usuario (YouTube/Instagram/TikTok)
-- Idempotente: IF NOT EXISTS + DO blocks
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabla social_accounts
CREATE TABLE IF NOT EXISTS social_accounts (
    id                      UUID                        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID                        NOT NULL,
    platform                VARCHAR(20)                 NOT NULL,
    platform_account_id     VARCHAR(255)                NOT NULL,
    platform_username       VARCHAR(255)                NOT NULL,
    access_token            TEXT                        NOT NULL,
    refresh_token           TEXT                        NOT NULL,
    token_expires_at        TIMESTAMP WITH TIME ZONE,
    created_at              TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_social_accounts_user
        FOREIGN KEY (user_id) REFERENCES usuarios (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT chk_social_accounts_platform
        CHECK (lower(platform) IN ('youtube', 'instagram', 'tiktok')),

    CONSTRAINT uq_social_accounts_user_platform
        UNIQUE (user_id, platform)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_social_accounts_user_id ON social_accounts (user_id);
CREATE INDEX IF NOT EXISTS idx_social_accounts_platform ON social_accounts (platform);

-- Trigger updated_at (reusa set_updated_at() de 01-init-schema.sql)
DROP TRIGGER IF EXISTS trg_social_accounts_set_updated_at ON social_accounts;
CREATE TRIGGER trg_social_accounts_set_updated_at
    BEFORE UPDATE ON social_accounts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE social_accounts IS 'Cuentas OAuth vinculadas (YouTube/Instagram/TikTok) por usuario.';
COMMENT ON COLUMN social_accounts.platform IS 'Plataforma: youtube | instagram | tiktok';
COMMENT ON COLUMN social_accounts.token_expires_at IS 'Expiración del access_token, nullable si no expira.';
