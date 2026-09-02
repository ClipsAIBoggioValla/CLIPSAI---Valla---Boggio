import pg from 'pg'
import dotenv from 'dotenv'

dotenv.config()

function buildConnectionString(): string {
  const url = process.env.DATABASE_URL
  if (url) {
    return url.replace('postgresql+psycopg2://', 'postgresql://')
  }
  const user = process.env.POSTGRES_USER ?? 'clipsai'
  const password = process.env.POSTGRES_PASSWORD ?? 'changeme'
  const db = process.env.POSTGRES_DB ?? 'clipsai'
  const host = process.env.DB_HOST ?? 'db'
  const port = process.env.POSTGRES_PORT ?? '5432'
  return `postgresql://${user}:${password}@${host}:${port}/${db}`
}

export const pool = new pg.Pool({
  connectionString: buildConnectionString(),
})
