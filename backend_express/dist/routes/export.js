import { Router } from 'express';
import { pool } from '../db/index.js';
import { authMiddleware } from '../middleware/auth.js';
export const exportRouter = Router();
function resolveTranscript(row) {
    for (const attr of ['transcript', 'transcript_text', 'transcription', 'text']) {
        const v = row[attr];
        if (typeof v === 'string' && v)
            return v;
    }
    const tags = row.tags;
    if (tags && typeof tags === 'object' && !Array.isArray(tags)) {
        const t = tags;
        if (typeof t.transcript === 'string' && t.transcript)
            return t.transcript;
        if (typeof t.text === 'string' && t.text)
            return t.text;
    }
    const vt = row.video_transcript;
    if (typeof vt === 'string' && vt)
        return vt;
    return '';
}
function escapeCsvField(value) {
    if (value.includes('"') || value.includes(',') || value.includes('\n') || value.includes('\r')) {
        return '"' + value.replace(/"/g, '""') + '"';
    }
    return value;
}
function buildCsv(rows) {
    const header = ['ID', 'Título', 'Inicio', 'Fin', 'Score', 'Transcripción'].map(escapeCsvField).join(',');
    const lines = [header];
    for (const r of rows) {
        const transcript = resolveTranscript(r);
        const score = r.score !== null && r.score !== undefined ? String(r.score) : '';
        const fields = [
            String(r.id),
            r.title ?? '',
            String(r.start_time),
            String(r.end_time),
            score,
            transcript,
        ].map(escapeCsvField);
        lines.push(fields.join(','));
    }
    return lines.join('\n') + '\n';
}
function buildJsonPayload(rows, jobId) {
    const clips = rows.map((r) => ({
        id: String(r.id),
        title: r.title ?? null,
        start_time: Number(r.start_time),
        end_time: Number(r.end_time),
        score: r.score !== null && r.score !== undefined ? Number(r.score) : null,
        transcript: resolveTranscript(r),
    }));
    const payload = {
        total_clips: clips.length,
        clips,
    };
    if (jobId)
        payload.job_id = jobId;
    const scores = rows.map((r) => r.score).filter((s) => s !== null && s !== undefined).map(Number).filter((n) => !Number.isNaN(n));
    if (scores.length > 0) {
        payload.avg_score = Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 100) / 100;
    }
    return payload;
}
function isValidUuid(v) {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v);
}
async function handleJobExport(req, res) {
    const userId = req.user.id;
    const jobId = String(req.params.jobId ?? req.params.job_id ?? '');
    const format = String(req.query.format ?? '');
    if (!isValidUuid(jobId)) {
        return res.status(422).json({ detail: 'job_id debe ser UUID válido' });
    }
    if (format !== 'csv' && format !== 'json') {
        return res.status(422).json({ detail: "format debe ser 'csv' o 'json'" });
    }
    const client = await pool.connect();
    try {
        const jobRes = await client.query(`SELECT j.id, v.usuario_id FROM jobs j JOIN videos v ON j.video_id = v.id WHERE j.id = $1`, [jobId]);
        if (jobRes.rows.length === 0) {
            return res.status(404).json({ detail: 'Job no encontrado' });
        }
        if (String(jobRes.rows[0].usuario_id) !== String(userId)) {
            return res.status(404).json({ detail: 'Job no encontrado' });
        }
        const clipsRes = await client.query(`SELECT c.id, c.title, c.start_time, c.end_time, c.score, c.tags,
              v.transcript AS video_transcript
       FROM clips c
       JOIN jobs j ON c.job_id = j.id
       JOIN videos v ON j.video_id = v.id
       WHERE c.job_id = $1
       ORDER BY c.start_time ASC`, [jobId]);
        const rows = clipsRes.rows;
        if (format === 'csv') {
            const csv = buildCsv(rows);
            res.setHeader('Content-Type', 'text/csv; charset=utf-8');
            res.setHeader('Content-Disposition', 'attachment; filename="clips_export.csv"');
            return res.send(csv);
        }
        const payload = buildJsonPayload(rows, jobId);
        const json = JSON.stringify(payload, null, 2);
        res.setHeader('Content-Type', 'application/json');
        res.setHeader('Content-Disposition', 'attachment; filename="clips_export.json"');
        return res.send(json);
    }
    catch (err) {
        console.error('export job error', err);
        return res.status(500).json({ detail: 'Error interno' });
    }
    finally {
        client.release();
    }
}
async function handleClipsExport(req, res) {
    const userId = req.user.id;
    const format = String(req.query.format ?? '');
    if (format !== 'csv' && format !== 'json') {
        return res.status(422).json({ detail: "format debe ser 'csv' o 'json'" });
    }
    const client = await pool.connect();
    try {
        const clipsRes = await client.query(`SELECT c.id, c.title, c.start_time, c.end_time, c.score, c.tags,
              v.transcript AS video_transcript
       FROM clips c
       JOIN jobs j ON c.job_id = j.id
       JOIN videos v ON j.video_id = v.id
       WHERE v.usuario_id = $1
       ORDER BY c.start_time ASC`, [userId]);
        const rows = clipsRes.rows;
        if (format === 'csv') {
            const csv = buildCsv(rows);
            res.setHeader('Content-Type', 'text/csv; charset=utf-8');
            res.setHeader('Content-Disposition', 'attachment; filename="clips_export.csv"');
            return res.send(csv);
        }
        const payload = buildJsonPayload(rows);
        const json = JSON.stringify(payload, null, 2);
        res.setHeader('Content-Type', 'application/json');
        res.setHeader('Content-Disposition', 'attachment; filename="clips_export.json"');
        return res.send(json);
    }
    catch (err) {
        console.error('export clips error', err);
        return res.status(500).json({ detail: 'Error interno' });
    }
    finally {
        client.release();
    }
}
exportRouter.get('/clips/export', authMiddleware, handleClipsExport);
exportRouter.get('/jobs/:jobId/export', authMiddleware, handleJobExport);
exportRouter.get('/api/v1/jobs/:jobId/export', authMiddleware, handleJobExport);
