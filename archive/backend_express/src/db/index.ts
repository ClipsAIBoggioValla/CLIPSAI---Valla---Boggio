import pg from 'pg'
import dotenv from 'dotenv'
import fs from 'fs'

dotenv.config()
try {
  dotenv.config({ path: '../.env' })
} catch {}
try {
  dotenv.config({ path: '../../.env' })
} catch {}

function isDocker(): boolean {
  try {
    return fs.existsSync('/.dockerenv')
  } catch {
    return false
  }
}

function hasDbHostPattern(url: string): boolean {
  return url.includes('@db:') || url.includes('@db/')
}

function hasLocalHostPattern(url: string): boolean {
  return url.includes('@127.0.0.1:') || url.includes('@localhost:')
}

function dockerLocalUrl(url: string): string {
  return url.replace('@127.0.0.1:', '@db:').replace('@localhost:', '@db:').replace('@127.0.0.1/', '@db/')
}

function localDbUrl(url: string): string {
  return url.replace('@db:', '@127.0.0.1:').replace('@db/', '@127.0.0.1/')
}

function resolveDbHost(url: string): string {
  const docker = isDocker()
  if (docker && hasLocalHostPattern(url)) return dockerLocalUrl(url)
  if (!docker && hasDbHostPattern(url)) return localDbUrl(url)
  return url
}

function connectionFromEnv(): string {
  const raw = process.env.DATABASE_URL
  if (!raw) return ''
  const url = raw.replace('postgresql+psycopg2://', 'postgresql://')
  return resolveDbHost(url)
}

function envOrDefault(name: string, fallback: string): string {
  return process.env[name] ?? fallback
}

function connectionFromParts(): string {
  const user = envOrDefault('POSTGRES_USER', 'postgres')
  const password = envOrDefault('POSTGRES_PASSWORD', 'postgres')
  const db = envOrDefault('POSTGRES_DB', 'clipsai')
  const hostDefault = isDocker() ? 'db' : '127.0.0.1'
  const host = envOrDefault('DB_HOST', hostDefault)
  const port = envOrDefault('POSTGRES_PORT', '5432')
  return `postgresql://${user}:${password}@${host}:${port}/${db}`
}

function buildConnectionString(): string {
  const fromEnv = connectionFromEnv()
  if (fromEnv) return fromEnv
  return connectionFromParts()
}

export const pool = new pg.Pool({
  connectionString: buildConnectionString(),
})
