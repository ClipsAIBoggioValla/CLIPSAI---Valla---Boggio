-- =============================================================================
-- clipsai — DDL inicial (Issue 1)
-- -----------------------------------------------------------------------------
-- Este script se ejecuta automaticamente por el contenedor `clipsai-db` la
-- PRIMERA vez que arranca contra un volumen `postgres_data` vacio.
-- Para re-ejecutarlo: `docker compose down -v && docker compose up -d`.
--
-- Relaciones (ver ISSUES.md — Issue 1):
--     usuarios 1---N videos 1---N jobs 1---N clips
--
-- El script es 100% idempotente: puede aplicarse manualmente varias veces
-- sin fallar (uso de IF NOT EXISTS, bloques DO ... EXCEPTION, etc).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Extensiones
-- -----------------------------------------------------------------------------
-- uuid-ossp provee uuid_generate_v4() para PKs.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- -----------------------------------------------------------------------------
-- Utilidad: trigger para mantener `updated_at` sincronizado
-- -----------------------------------------------------------------------------
-- Se aplica a las 4 tablas via triggers BEFORE UPDATE. Asi el backend nunca
-- tiene que acordarse de actualizar el timestamp a mano.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- Tabla: usuarios
-- Cuentas de usuario del sistema clipsai.
-- =============================================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id                  UUID                        PRIMARY KEY DEFAULT uuid_generate_v4(),
    email               VARCHAR(255)                NOT NULL UNIQUE,
    hashed_password     VARCHAR(255)                NOT NULL,   -- bcrypt (Issue 3)
    full_name           VARCHAR(100),
    created_at          TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Trigger de updated_at
DROP TRIGGER IF EXISTS trg_usuarios_set_updated_at ON usuarios;
CREATE TRIGGER trg_usuarios_set_updated_at
    BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- Tabla: videos
-- Videos crudos subidos por un usuario, junto con su transcripcion.
-- =============================================================================
CREATE TABLE IF NOT EXISTS videos (
    id                      UUID                        PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id              UUID                        NOT NULL,
    original_filename       VARCHAR(255)                NOT NULL,
    file_path               TEXT                        NOT NULL,
    duration_seconds        FLOAT,
    transcript              TEXT,
    created_at              TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_videos_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- Indice B-Tree en la FK -> optimiza JOINs y busquedas "videos de un usuario"
CREATE INDEX IF NOT EXISTS idx_videos_usuario_id ON videos (usuario_id);

-- Trigger de updated_at
DROP TRIGGER IF EXISTS trg_videos_set_updated_at ON videos;
CREATE TRIGGER trg_videos_set_updated_at
    BEFORE UPDATE ON videos
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- Tabla: jobs
-- Ejecuciones del pipeline de procesamiento sobre un video.
-- =============================================================================
CREATE TABLE IF NOT EXISTS jobs (
    id                  UUID                        PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id            UUID                        NOT NULL,
    status              VARCHAR(50)                 NOT NULL DEFAULT 'pending',
    error_message       TEXT,
    created_at          TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_jobs_video
        FOREIGN KEY (video_id) REFERENCES videos (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    -- Valida el dominio de `status` en la propia DB (defense in depth).
    CONSTRAINT chk_jobs_status
        CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);

-- Indice B-Tree en la FK
CREATE INDEX IF NOT EXISTS idx_jobs_video_id ON jobs (video_id);

-- Trigger de updated_at
DROP TRIGGER IF EXISTS trg_jobs_set_updated_at ON jobs;
CREATE TRIGGER trg_jobs_set_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- Tabla: clips
-- Clips virales generados por un job, con metadata editable y estado de
-- publicacion en redes sociales (Issues 5, 10, 11, 12).
-- =============================================================================
CREATE TABLE IF NOT EXISTS clips (
    id                      UUID                        PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id                  UUID                        NOT NULL,
    title                   VARCHAR(255),
    file_path               TEXT                        NOT NULL,
    start_time              FLOAT                       NOT NULL,
    end_time                FLOAT                       NOT NULL,
    social_network          VARCHAR(50),                            -- tiktok | youtube_shorts | instagram_reels | NULL
    publication_status      VARCHAR(50)                 NOT NULL DEFAULT 'draft',
    published_at            TIMESTAMP WITH TIME ZONE,
    created_at              TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_clips_job
        FOREIGN KEY (job_id) REFERENCES jobs (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    -- Valida el rango temporal del clip.
    CONSTRAINT chk_clips_time_range
        CHECK (end_time > start_time AND start_time >= 0),

    -- Valida el dominio de `publication_status`.
    CONSTRAINT chk_clips_publication_status
        CHECK (publication_status IN ('draft', 'scheduled', 'published', 'failed')),

    -- Valida el dominio de `social_network` (permite NULL).
    CONSTRAINT chk_clips_social_network
        CHECK (social_network IS NULL
               OR social_network IN ('tiktok', 'youtube_shorts', 'instagram_reels'))
);

-- Indice B-Tree en la FK
CREATE INDEX IF NOT EXISTS idx_clips_job_id ON clips (job_id);

-- Trigger de updated_at
DROP TRIGGER IF EXISTS trg_clips_set_updated_at ON clips;
CREATE TRIGGER trg_clips_set_updated_at
    BEFORE UPDATE ON clips
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- Comentarios (visibles con `\d+ <tabla>` en psql)
-- =============================================================================
COMMENT ON TABLE  usuarios                      IS 'Cuentas de usuario del sistema clipsai.';
COMMENT ON TABLE  videos                        IS 'Videos subidos por un usuario con su transcripcion.';
COMMENT ON TABLE  jobs                          IS 'Ejecuciones del pipeline de generacion de clips.';
COMMENT ON TABLE  clips                         IS 'Clips virales generados con metadata y estado de publicacion.';

COMMENT ON COLUMN jobs.status                   IS 'Estado del job: pending | processing | completed | failed.';
COMMENT ON COLUMN clips.social_network          IS 'Red social objetivo: tiktok | youtube_shorts | instagram_reels.';
COMMENT ON COLUMN clips.publication_status      IS 'Estado de publicacion: draft | scheduled | published | failed.';
