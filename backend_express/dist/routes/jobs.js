import { Router } from 'express';
import { pool } from '../db/index.js';
import { authMiddleware } from '../middleware/auth.js';
export const jobsRouter = Router();
function isValidUuid(v) {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v);
}
function parseTimeToSeconds(value) {
    if (value === null || value === undefined)
        return 0;
    if (typeof value === 'number')
        return value;
    const s = String(value).trim();
    if (!s)
        return 0;
    try {
        if (s.includes(':')) {
            const parts = s.split(':');
            if (parts.length === 3)
                return parseInt(parts[0], 10) * 3600 + parseInt(parts[1], 10) * 60 + parseFloat(parts[2]);
            if (parts.length === 2)
                return parseInt(parts[0], 10) * 60 + parseFloat(parts[1]);
        }
        return parseFloat(s);
    }
    catch {
        return 0;
    }
}
async function runClipEngine(videoPath, transcriptionPath) {
    const fs = await import('fs');
    if (!fs.existsSync(videoPath) || !fs.existsSync(transcriptionPath)) {
        throw new Error('Video o transcripción no encontrada');
    }
    // Try real Python engine via child_process, fallback to simulated
    try {
        const { spawnSync } = await import('child_process');
        const path = await import('path');
        const root = path.resolve(process.cwd(), '..');
        const enginePath = path.join(root, 'engine.py');
        if (fs.existsSync(enginePath)) {
            const res = spawnSync('python', [enginePath, videoPath, transcriptionPath, '--json'], { timeout: 10000, encoding: 'utf-8' });
            if (res.status === 0 && res.stdout) {
                try {
                    const parsed = JSON.parse(res.stdout);
                    if (parsed?.clips)
                        return parsed;
                }
                catch { }
            }
        }
    }
    catch { }
    // Fallback simulated (paridad con FastAPI simulado)
    await new Promise((r) => setTimeout(r, 800));
    let preview = '';
    try {
        const fs2 = await import('fs');
        preview = fs2.readFileSync(transcriptionPath, 'utf-8').slice(0, 100);
    }
    catch { }
    return {
        clips: [
            { inicio: '00:00:10', fin: '00:00:55', titulo: 'Clip simulado 1', score: 8, transcript_preview: preview },
            { inicio: '00:01:00', fin: '00:01:40', titulo: 'Clip simulado 2', score: 7 },
        ],
        engine: 'simulated',
    };
}
async function runJob(jobId) {
    const client = await pool.connect();
    try {
        await client.query("UPDATE jobs SET status = 'processing', updated_at = NOW() WHERE id = $1", [jobId]);
        const jobRes = await client.query('SELECT video_id FROM jobs WHERE id = $1', [jobId]);
        if (jobRes.rows.length === 0)
            return;
        const videoId = jobRes.rows[0].video_id;
        const videoRes = await client.query('SELECT file_path, transcription_filepath, transcript FROM videos WHERE id = $1', [videoId]);
        if (videoRes.rows.length === 0)
            throw new Error('Video asociado no encontrado');
        const video = videoRes.rows[0];
        const videoPath = video.file_path;
        const transcriptionPath = video.transcription_filepath || '';
        const result = await runClipEngine(videoPath, transcriptionPath);
        const clipsPayload = Array.isArray(result.clips)
            ? result.clips
            : Array.isArray(result)
                ? result
                : [];
        // Fetch fresh job to ensure exists
        const fresh = await client.query('SELECT id FROM jobs WHERE id = $1', [jobId]);
        if (fresh.rows.length === 0)
            return;
        await client.query('UPDATE jobs SET result_metadata = $1::jsonb, status = $2, error_message = NULL, updated_at = NOW() WHERE id = $3', [
            JSON.stringify(result),
            'completed',
            jobId,
        ]);
        for (const item of clipsPayload) {
            if (typeof item !== 'object' || item === null)
                continue;
            const title = item.title || item.titulo || item.titulo_sugerido || 'Clip';
            const startRaw = item.start_time ?? item.inicio ?? 0;
            const endRaw = item.end_time ?? item.fin ?? 10;
            let start = parseTimeToSeconds(startRaw);
            let end = parseTimeToSeconds(endRaw);
            if (end <= start)
                end = start + 30;
            const score = item.score !== undefined && item.score !== null ? Number(item.score) : null;
            const tags = Array.isArray(item.tags) ? item.tags : item.tags ? [String(item.tags)] : null;
            const storage = item.storage_path || item.file_path || '';
            await client.query('INSERT INTO clips (video_id, job_id, title, start_time, end_time, score, tags, file_path, status) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9)', [videoId, jobId, String(title).slice(0, 255), start, end, score, tags ? JSON.stringify(tags) : null, storage, 'ready']);
        }
    }
    catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        try {
            await pool.query("UPDATE jobs SET status = 'failed', error_message = $1, updated_at = NOW() WHERE id = $2", [msg.slice(0, 2000), jobId]);
        }
        catch { }
    }
    finally {
        client.release();
    }
}
jobsRouter.post('/videos/:videoId/jobs', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    const videoId = String(req.params.videoId);
    if (!isValidUuid(videoId))
        return res.status(422).json({ detail: 'video_id debe ser UUID válido' });
    if (!isValidUuid(userId))
        return res.status(401).json({ detail: 'Usuario inválido' });
    const client = await pool.connect();
    try {
        const vRes = await client.query('SELECT id, usuario_id FROM videos WHERE id = $1', [videoId]);
        if (vRes.rows.length === 0)
            return res.status(404).json({ detail: 'Video no encontrado' });
        if (String(vRes.rows[0].usuario_id) !== String(userId))
            return res.status(403).json({ detail: 'No autorizado para este video' });
        const jRes = await client.query("INSERT INTO jobs (video_id, status) VALUES ($1,'pending') RETURNING id, video_id, status, error_message, result_metadata, created_at, updated_at", [videoId]);
        const job = jRes.rows[0];
        const jobId = String(job.id);
        setImmediate(() => {
            runJob(jobId).catch((e) => console.error('runJob error', e));
        });
        return res.status(202).json({
            id: job.id,
            video_id: job.video_id,
            status: String(job.status).toUpperCase(),
            error_message: job.error_message ?? null,
            result_metadata: job.result_metadata ?? null,
            created_at: new Date(job.created_at).toISOString(),
            updated_at: new Date(job.updated_at).toISOString(),
        });
    }
    catch (err) {
        console.error('POST /videos/:videoId/jobs error', err);
        return res.status(500).json({ detail: 'Error interno' });
    }
    finally {
        client.release();
    }
});
jobsRouter.get('/jobs/:jobId', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    const jobId = String(req.params.jobId);
    if (!isValidUuid(jobId))
        return res.status(422).json({ detail: 'job_id debe ser UUID válido' });
    try {
        const jRes = await pool.query('SELECT j.id, j.video_id, j.status, j.error_message, j.result_metadata, j.created_at, j.updated_at, v.usuario_id FROM jobs j JOIN videos v ON j.video_id = v.id WHERE j.id = $1', [jobId]);
        if (jRes.rows.length === 0)
            return res.status(404).json({ detail: 'Job no encontrado' });
        const row = jRes.rows[0];
        if (String(row.usuario_id) !== String(userId))
            return res.status(404).json({ detail: 'Job no encontrado' });
        return res.json({
            id: row.id,
            video_id: row.video_id,
            status: String(row.status).toUpperCase(),
            error_message: row.error_message ?? null,
            result_metadata: row.result_metadata ?? null,
            created_at: new Date(row.created_at).toISOString(),
            updated_at: new Date(row.updated_at).toISOString(),
        });
    }
    catch (err) {
        console.error('GET /jobs/:jobId error', err);
        return res.status(500).json({ detail: 'Error interno' });
    }
});
jobsRouter.get('/jobs/:jobId/stream', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    const jobId = String(req.params.jobId);
    if (!isValidUuid(jobId))
        return res.status(422).json({ detail: 'job_id debe ser UUID válido' });
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    // @ts-ignore
    if (typeof res.flushHeaders === 'function')
        res.flushHeaders();
    const STATUS_MAP = {
        pending: { progress: 0, status: 'pending', message: 'En cola' },
        processing: { progress: 55, status: 'scoring', message: 'Procesando con IA' },
        completed: { progress: 100, status: 'completed', message: 'Completado' },
        failed: { progress: 100, status: 'failed', message: 'Falló' },
    };
    let lastStatus = null;
    const interval = setInterval(async () => {
        try {
            const r = await pool.query('SELECT j.status, j.error_message, v.usuario_id FROM jobs j JOIN videos v ON j.video_id = v.id WHERE j.id = $1', [jobId]);
            if (r.rows.length === 0) {
                res.write(`event: error\ndata: ${JSON.stringify({ detail: 'Job no encontrado' })}\n\n`);
                clearInterval(interval);
                res.end();
                return;
            }
            const row = r.rows[0];
            if (String(row.usuario_id) !== String(userId)) {
                res.write(`event: error\ndata: ${JSON.stringify({ detail: 'No autorizado' })}\n\n`);
                clearInterval(interval);
                res.end();
                return;
            }
            const raw = String(row.status);
            if (raw === lastStatus)
                return;
            lastStatus = raw;
            const mapped = STATUS_MAP[raw.toLowerCase()] ?? { progress: 0, status: raw, message: raw };
            const payload = { progress: mapped.progress, status: mapped.status, message: mapped.message, job_id: jobId };
            if (row.error_message)
                payload.error = row.error_message;
            res.write(`data: ${JSON.stringify(payload)}\n\n`);
            if (raw.toLowerCase() === 'completed' || raw.toLowerCase() === 'failed') {
                res.write('event: done\ndata: {}\n\n');
                clearInterval(interval);
                res.end();
            }
        }
        catch (e) {
            console.error('SSE stream error', e);
            clearInterval(interval);
            res.end();
        }
    }, 1000);
    req.on('close', () => {
        clearInterval(interval);
    });
});
