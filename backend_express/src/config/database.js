const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/clipsai_db',
});

async function migrate() {
  const statements = [
    'ALTER TABLE videos ADD COLUMN IF NOT EXISTS transcription_filepath VARCHAR;',
    'ALTER TABLE videos ADD COLUMN IF NOT EXISTS transcript TEXT;',
    'ALTER TABLE videos ADD COLUMN IF NOT EXISTS duration_seconds DOUBLE PRECISION;',
    'ALTER TABLE jobs ADD COLUMN IF NOT EXISTS result_metadata JSONB;',
    'ALTER TABLE jobs ADD COLUMN IF NOT EXISTS error_message TEXT;',
    'ALTER TABLE clips ADD COLUMN IF NOT EXISTS video_id UUID;',
    'ALTER TABLE clips ADD COLUMN IF NOT EXISTS score DOUBLE PRECISION;',
    'ALTER TABLE clips ADD COLUMN IF NOT EXISTS tags JSONB;',
    "ALTER TABLE clips ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'ready';",
    'ALTER TABLE clips ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;',
    'ALTER TABLE jobs DROP CONSTRAINT IF EXISTS chk_jobs_status;',
    'ALTER TABLE jobs DROP CONSTRAINT IF EXISTS chk_jobs_stats;',
    `DO $$ BEGIN
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='chk_jobs_status') THEN
         ALTER TABLE jobs ADD CONSTRAINT chk_jobs_status
         CHECK (lower(status) IN ('pending','processing','completed','failed'));
       END IF;
     END $$;`,
  ];

  for (const stmt of statements) {
    try {
      await pool.query(stmt);
    } catch (err) {
      console.warn('Migration skipped (non-fatal):', err.message);
    }
  }
}

module.exports = {
  query: (text, params) => pool.query(text, params),
  pool,
  migrate,
};
