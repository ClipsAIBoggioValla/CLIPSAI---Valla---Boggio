import { Router } from 'express';
import fs from 'fs';
import path from 'path';
import { pool } from '../db/index.js';
import { authMiddleware } from '../middleware/auth.js';
export const clipsRouter = Router();
const SORT_MAP = {
    created_at_desc: 'c.created_at DESC',
    created_at_asc: 'c.created_at ASC',
    score_desc: 'c.score DESC NULLS LAST, c.created_at DESC',
    score_asc: 'c.score ASC NULLS LAST, c.created_at DESC',
};
function isValidUuid(v) {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v);
}
clipsRouter.get('/', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    const q = typeof req.query.q === 'string' ? req.query.q.trim() : undefined;
    const minScoreRaw = req.query.min_score;
    const min_score = minScoreRaw !== undefined && minScoreRaw !== '' ? Number(minScoreRaw) : undefined;
    const sort_by = (typeof req.query.sort_by === 'string' ? req.query.sort_by : 'created_at_desc');
    const page = Math.max(1, parseInt(String(req.query.page ?? '1'), 10) || 1);
    const limit = Math.min(100, Math.max(1, parseInt(String(req.query.limit ?? '10'), 10) || 10));
    const videoIdRaw = typeof req.query.video_id === 'string' ? req.query.video_id : undefined;
    const statusRaw = typeof req.query.status === 'string' ? req.query.status : undefined;
    if (min_score !== undefined && (Number.isNaN(min_score) || min_score < 0 || min_score > 100)) {
        return res.status(422).json({ detail: 'min_score must be between 0 and 100' });
    }
    const orderBy = SORT_MAP[sort_by];
    if (!orderBy) {
        return res.status(422).json({ detail: 'sort_by must be one of created_at_desc, created_at_asc, score_desc, score_asc' });
    }
    if (videoIdRaw && !isValidUuid(videoIdRaw))
        return res.status(422).json({ detail: 'video_id debe ser UUID válido' });
    const conditions = ['v.usuario_id = $1'];
    const values = [userId];
    let paramIdx = 2;
    if (q) {
        conditions.push(`(c.title ILIKE $${paramIdx} OR v.transcript ILIKE $${paramIdx})`);
        values.push(`%${q}%`);
        paramIdx += 1;
    }
    if (min_score !== undefined) {
        conditions.push(`c.score >= $${paramIdx}`);
        values.push(min_score);
        paramIdx += 1;
    }
    if (videoIdRaw) {
        conditions.push(`(c.video_id = $${paramIdx} OR j.video_id = $${paramIdx})`);
        values.push(videoIdRaw);
        paramIdx += 1;
    }
    if (statusRaw) {
        conditions.push(`c.status = $${paramIdx}`);
        values.push(statusRaw);
        paramIdx += 1;
    }
    const whereClause = conditions.join(' AND ');
    const client = await pool.connect();
    try {
        const countRes = await client.query(`SELECT COUNT(*)::int AS total
       FROM clips c
       JOIN jobs j ON c.job_id = j.id
       JOIN videos v ON j.video_id = v.id
       WHERE ${whereClause}`, values);
        const total = countRes.rows[0]?.total ?? 0;
        const total_pages = total > 0 ? Math.ceil(total / limit) : 0;
        const offset = (page - 1) * limit;
        const dataRes = await client.query(`SELECT
         c.id, c.job_id, c.title, c.score, c.start_time, c.end_time,
         LEFT(v.transcript, 500) AS transcript,
         c.created_at
       FROM clips c
       JOIN jobs j ON c.job_id = j.id
       JOIN videos v ON j.video_id = v.id
       WHERE ${whereClause}
       ORDER BY ${orderBy}
       LIMIT $${paramIdx} OFFSET $${paramIdx + 1}`, [...values, limit, offset]);
        const items = dataRes.rows.map((r) => ({
            id: r.id,
            job_id: r.job_id,
            title: r.title,
            score: r.score !== null && r.score !== undefined ? Number(r.score) : null,
            start_time: Number(r.start_time),
            end_time: Number(r.end_time),
            transcript: r.transcript ?? null,
            created_at: new Date(r.created_at).toISOString(),
        }));
        return res.json({ items, total, page, limit, total_pages });
    }
    catch (err) {
        console.error('GET /clips error', err);
        return res.status(500).json({ detail: 'Error interno' });
    }
    finally {
        client.release();
    }
});
async function getClipOr404(clipId, userId, client) {
    if (!isValidUuid(clipId))
        throw { status: 422, detail: 'clip_id debe ser UUID válido' };
    const r = await client.query(`SELECT c.*, j.video_id AS job_video_id, v.usuario_id, v.file_path AS video_filepath
     FROM clips c
     JOIN jobs j ON c.job_id = j.id
     JOIN videos v ON j.video_id = v.id
     WHERE c.id = $1`, [clipId]);
    if (r.rows.length === 0)
        throw { status: 404, detail: 'Clip no encontrado' };
    const row = r.rows[0];
    if (String(row.usuario_id) !== String(userId))
        throw { status: 404, detail: 'Clip no encontrado' };
    return row;
}
clipsRouter.get('/:clipId', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    const clipId = String(req.params.clipId);
    const client = await pool.connect();
    try {
        const row = await getClipOr404(clipId, String(userId), client);
        return res.json({
            id: row.id,
            video_id: row.video_id,
            job_id: row.job_id,
            title: row.title,
            start_time: Number(row.start_time),
            end_time: Number(row.end_time),
            score: row.score !== null ? Number(row.score) : null,
            tags: row.tags ?? null,
            storage_path: row.file_path,
            status: row.status,
            created_at: new Date(row.created_at).toISOString(),
            updated_at: new Date(row.updated_at ?? row.created_at).toISOString(),
        });
    }
    catch (e) {
        const err = e;
        if (err?.status)
            return res.status(err.status).json({ detail: err.detail });
        console.error('GET /clips/:id error', e);
        return res.status(500).json({ detail: 'Error interno' });
    }
    finally {
        client.release();
    }
});
clipsRouter.patch('/:clipId', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    const clipId = String(req.params.clipId);
    const { title, tags } = req.body;
    if (title === undefined && tags === undefined)
        return res.status(400).json({ detail: 'Nada para actualizar' });
    if (title !== undefined && title !== null && typeof title !== 'string')
        return res.status(422).json({ detail: 'title debe ser string' });
    if (tags !== undefined && tags !== null && !Array.isArray(tags))
        return res.status(422).json({ detail: 'tags debe ser array' });
    const client = await pool.connect();
    try {
        await getClipOr404(clipId, String(userId), client);
        const updates = [];
        const values = [];
        let idx = 1;
        if (title !== undefined) {
            updates.push(`title = $${idx++}`);
            values.push(title ?? null);
        }
        if (tags !== undefined) {
            updates.push(`tags = $${idx++}`);
            values.push(tags ? JSON.stringify(tags) : null);
        }
        values.push(clipId);
        const q = `UPDATE clips SET ${updates.join(', ')}, updated_at = NOW() WHERE id = $${idx} RETURNING id, video_id, job_id, title, start_time, end_time, score, tags, file_path, status, created_at, updated_at`;
        const r = await client.query(q, values);
        const row = r.rows[0];
        return res.json({
            id: row.id,
            video_id: row.video_id,
            job_id: row.job_id,
            title: row.title,
            start_time: Number(row.start_time),
            end_time: Number(row.end_time),
            score: row.score !== null ? Number(row.score) : null,
            tags: row.tags ?? null,
            storage_path: row.file_path,
            status: row.status,
            created_at: new Date(row.created_at).toISOString(),
            updated_at: new Date(row.updated_at).toISOString(),
        });
    }
    catch (e) {
        const err = e;
        if (err?.status)
            return res.status(err.status).json({ detail: err.detail });
        console.error('PATCH /clips/:id error', e);
        return res.status(500).json({ detail: 'Error interno' });
    }
    finally {
        client.release();
    }
});
clipsRouter.delete('/:clipId', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    const clipId = String(req.params.clipId);
    const client = await pool.connect();
    try {
        const row = await getClipOr404(clipId, String(userId), client);
        const filePath = row.file_path;
        if (filePath) {
            try {
                const p = path.resolve(filePath);
                if (fs.existsSync(p))
                    fs.unlinkSync(p);
            }
            catch { }
        }
        await client.query('DELETE FROM clips WHERE id = $1', [clipId]);
        return res.status(204).send();
    }
    catch (e) {
        const err = e;
        if (err?.status)
            return res.status(err.status).json({ detail: err.detail });
        console.error('DELETE /clips/:id error', e);
        return res.status(500).json({ detail: 'Error interno' });
    }
    finally {
        client.release();
    }
});
clipsRouter.get('/:clipId/descarga', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    const clipId = String(req.params.clipId);
    const client = await pool.connect();
    try {
        const row = await getClipOr404(clipId, String(userId), client);
        const candidates = [];
        if (row.file_path)
            candidates.push(String(row.file_path));
        const videoPath = row.video_filepath;
        if (videoPath)
            candidates.push(videoPath);
        for (const p of candidates) {
            const abs = path.resolve(p);
            if (fs.existsSync(abs) && fs.statSync(abs).isFile()) {
                const filename = path.basename(abs) || `${clipId}.mp4`;
                const ext = path.extname(abs).toLowerCase();
                const media = ['.mp4', '.mov', '.avi', '.mkv'].includes(ext) ? 'video/mp4' : 'application/octet-stream';
                return res.download(abs, filename, { headers: { 'Content-Type': media } });
            }
        }
        const tmpDir = process.env.TMPDIR ?? '/tmp';
        const tmp = path.join(tmpDir, `clip_${clipId}.txt`);
        fs.mkdirSync(path.dirname(tmp), { recursive: true });
        fs.writeFileSync(tmp, `Clip ${row.id}\nTitle: ${row.title ?? ''}\nStart: ${row.start_time}\nEnd: ${row.end_time}\nStatus: ${row.status}\n`, 'utf-8');
        return res.download(tmp, `${clipId}.txt`);
    }
    catch (e) {
        const err = e;
        if (err?.status)
            return res.status(err.status).json({ detail: err.detail });
        console.error('GET /clips/:id/descarga error', e);
        return res.status(500).json({ detail: 'Error interno' });
    }
    finally {
        client.release();
    }
});
clipsRouter.post('/:clipId/retrim', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    const clipId = String(req.params.clipId);
    const { start_time, end_time } = req.body;
    const start = typeof start_time === 'number' ? start_time : Number(start_time);
    const end = typeof end_time === 'number' ? end_time : Number(end_time);
    if (Number.isNaN(start) || Number.isNaN(end) || start < 0 || end <= start)
        return res.status(422).json({ detail: 'start_time y end_time inválidos, end debe ser > start' });
    const duration = end - start;
    if (duration < 5)
        return res.status(422).json({ detail: 'Duración mínima 5s' });
    if (duration > 90)
        return res.status(422).json({ detail: 'Duración máxima 90s' });
    const client = await pool.connect();
    try {
        const row = await getClipOr404(clipId, String(userId), client);
        const candidates = [];
        if (row.file_path)
            candidates.push(String(row.file_path));
        if (row.video_filepath)
            candidates.push(String(row.video_filepath));
        let src = null;
        for (const p of candidates) {
            if (fs.existsSync(path.resolve(p))) {
                src = path.resolve(p);
                break;
            }
        }
        if (!src)
            src = candidates[0] ? path.resolve(candidates[0]) : null;
        if (!src || !fs.existsSync(src))
            return res.status(404).json({ detail: 'Video origen no encontrado para re-trim' });
        const outDir = path.join(process.cwd(), 'storage', 'retrims');
        fs.mkdirSync(outDir, { recursive: true });
        const outPath = path.join(outDir, `${clipId}_retrim_${Math.floor(start)}_${Math.floor(end)}.mp4`);
        const { spawnSync } = await import('child_process');
        const cmd = spawnSync('ffmpeg', ['-y', '-ss', String(start), '-i', src, '-t', String(duration), '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', outPath], { timeout: 120000 });
        if (cmd.status !== 0) {
            const detail = cmd.stderr ? cmd.stderr.toString().slice(0, 600) : 'FFmpeg error';
            return res.status(500).json({ detail: `FFmpeg re-trim falló: ${detail}` });
        }
        if (!fs.existsSync(outPath))
            return res.status(500).json({ detail: 'Re-trim no produjo archivo' });
        const r = await client.query('UPDATE clips SET start_time = $1, end_time = $2, file_path = $3, updated_at = NOW() WHERE id = $4 RETURNING id, start_time, end_time, file_path, status', [start, end, outPath, clipId]);
        const updated = r.rows[0];
        return res.json({
            clip_id: String(updated.id),
            start_time: Number(updated.start_time),
            end_time: Number(updated.end_time),
            duration,
            status: updated.status ?? 'ready',
            file_path: updated.file_path,
        });
    }
    catch (e) {
        const err = e;
        if (err?.status)
            return res.status(err.status).json({ detail: err.detail });
        console.error('POST /clips/:id/retrim error', e);
        return res.status(500).json({ detail: 'Error interno' });
    }
    finally {
        client.release();
    }
});
