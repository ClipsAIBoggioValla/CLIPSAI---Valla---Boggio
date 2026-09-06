import pg from 'pg';
import dotenv from 'dotenv';
import fs from 'fs';
dotenv.config();
try {
    dotenv.config({ path: '../.env' });
}
catch { }
try {
    dotenv.config({ path: '../../.env' });
}
catch { }
function isDocker() {
    try {
        return fs.existsSync('/.dockerenv');
    }
    catch {
        return false;
    }
}
function resolveDbHost(url) {
    if (!url.includes('@db:') && !url.includes('@db/'))
        return url;
    if (isDocker())
        return url;
    return url.replace('@db:', '@127.0.0.1:').replace('@db/', '@127.0.0.1/');
}
function buildConnectionString() {
    const raw = process.env.DATABASE_URL;
    if (raw) {
        let url = raw.replace('postgresql+psycopg2://', 'postgresql://');
        url = resolveDbHost(url);
        return url;
    }
    const user = process.env.POSTGRES_USER ?? 'postgres';
    const password = process.env.POSTGRES_PASSWORD ?? 'postgres';
    const db = process.env.POSTGRES_DB ?? 'clipsai';
    const hostDefault = isDocker() ? 'db' : '127.0.0.1';
    const host = process.env.DB_HOST ?? hostDefault;
    const port = process.env.POSTGRES_PORT ?? '5432';
    return `postgresql://${user}:${password}@${host}:${port}/${db}`;
}
export const pool = new pg.Pool({
    connectionString: buildConnectionString(),
});
