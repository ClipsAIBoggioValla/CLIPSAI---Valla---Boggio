const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/clipsai_db',
});

module.exports = {
  query: (text, params) => pool.query(text, params),
  pool,
};