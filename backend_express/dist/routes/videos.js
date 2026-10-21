import { Router } from 'express';
import multer from 'multer';
import fs from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';
import { pool } from '../db/index.js';
import { authMiddleware } from '../middleware/auth.js';
import { runJob } from './jobs.js';
export const videosRouter = Router();
const ALLOWED_VIDEO = new Set(['.mp4', '.mov', '.avi']);
const ALLOWED_TRANSCRIPT = new Set(['.txt', '.srt']);
const MAX_SIZE = 500 * 1024 * 1024;
function getUploadDir() {
    const candidates = [process.env.UPLOAD_DIR ?? '/storage/uploads', path.join(process.cwd(), 'storage', 'uploads')];
    for (const p of candidates) {
        try {
            fs.mkdirSync(p, { recursive: true });
            return p;
        }
        catch { }
    }
    const fallback = path.join(process.cwd(), 'storage', 'uploads');
    fs.mkdirSync(fallback, { recursive: true });
    return fallback;
}
const storage = multer.diskStorage({
    destination(_req, _file, cb) {
        cb(null, getUploadDir());
    },
    filename(_req, file, cb) {
        const ext = path.extname(file.originalname).toLowerCase();
        cb(null, `${randomUUID().replace(/-/g, '')}${ext}`);
    },
});
function fileFilter(_req, file, cb) {
    const ext = path.extname(file.originalname).toLowerCase();
    if (file.fieldname === 'video' && !ALLOWED_VIDEO.has(ext)) {
        return cb(new Error(`video: extension no permitida '${ext}'. Permitidas: ${[...ALLOWED_VIDEO].join(', ')}`));
    }
    if (file.fieldname === 'transcription' && !ALLOWED_TRANSCRIPT.has(ext)) {
        return cb(new Error(`transcription: extension no permitida '${ext}'. Permitidas: ${[...ALLOWED_TRANSCRIPT].join(', ')}`));
    }
    cb(null, true);
}
const upload = multer({
    storage,
    fileFilter,
    limits: { fileSize: MAX_SIZE },
});
function isValidUuid(v) {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v);
}
videosRouter.post('/', authMiddleware, upload.fields([
    { name: 'video', maxCount: 1 },
    { name: 'transcription', maxCount: 1 },
]), async (req, res) => {
    const userId = req.user.id;
    if (!isValidUuid(userId))
        return res.status(401).json({ detail: 'Usuario inválido' });
    const files = req.files;
    const videoFile = files?.video?.[0];
    const transcriptFile = files?.transcription?.[0];
    if (!videoFile) {
        if (transcriptFile?.path)
            try {
                fs.unlinkSync(transcriptFile.path);
            }
            catch { }
        return res.status(400).json({ detail: 'Se requiere archivo de video' });
    }
    let transcriptText = null;
    if (transcriptFile) {
        try {
            const raw = fs.readFileSync(transcriptFile.path, 'utf-8');
            transcriptText = raw.slice(0, 50000);
        }
        catch {
            transcriptText = null;
        }
    }
    try {
        const r = await pool.query('INSERT INTO videos (usuario_id, original_filename, file_path, transcription_filepath, transcript) VALUES ($1,$2,$3,$4,$5) RETURNING id, original_filename AS filename, created_at', [userId, videoFile.originalname || videoFile.filename, videoFile.path, transcriptFile?.path ?? null, transcriptText]);
        const row = r.rows[0];
        return res.status(201).json({ id: row.id, filename: row.filename, created_at: new Date(row.created_at).toISOString() });
    }
    catch (err) {
        try {
            fs.unlinkSync(videoFile.path);
        }
        catch { }
        if (transcriptFile?.path)
            try {
                fs.unlinkSync(transcriptFile.path);
            }
            catch { }
        console.error('POST /videos error', err);
        return res.status(500).json({ detail: 'Error interno' });
    }
});
/**
 * POST /videos/sample — Crear job con video de muestra (Issue 34)
 * Copia el video de muestra al directorio de uploads, crea video + job y lo ejecuta en background.
 * Responde 202 con JobResponse (id, video_id, status, progress, ...).
 */
videosRouter.post('/sample', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    if (!isValidUuid(userId))
        return res.status(401).json({ detail: 'Usuario inválido' });
    // Resolver ruta del video de muestra (igual que FastAPI)
    function resolveSamplePath() {
        const envPath = (process.env.SAMPLE_VIDEO_PATH || '').trim();
        if (envPath) {
            const p = path.resolve(envPath);
            if (fs.existsSync(p))
                return p;
        }
        // Candidatos por defecto
        const candidates = [
            path.join(process.cwd(), 'backend_fastapi', 'storage', 'sample', 'sample.mp4'),
            path.join(process.cwd(), '..', 'backend_fastapi', 'storage', 'sample', 'sample.mp4'),
            path.join(process.cwd(), 'storage', 'sample', 'sample.mp4'),
            path.join(process.cwd(), '..', 'storage', 'sample', 'sample.mp4'),
        ];
        for (const c of candidates) {
            if (fs.existsSync(c))
                return c;
        }
        // Retornar la ruta esperada para error descriptivo
        return candidates[0];
    }
    const samplePath = resolveSamplePath();
    if (!samplePath || !fs.existsSync(samplePath)) {
        return res.status(404).json({
            detail: `Video de muestra no encontrado en ${samplePath}. Colocá un archivo sample.mp4 en esa ubicación o configurá SAMPLE_VIDEO_PATH.`,
        });
    }
    // Copiar el video de muestra al directorio de uploads
    const uploadDir = getUploadDir();
    const dest = path.join(uploadDir, `sample_${randomUUID().replace(/-/g, '')}.mp4`);
    try {
        fs.copyFileSync(samplePath, dest);
    }
    catch (err) {
        console.error('Error copiando video de muestra:', err);
        return res.status(500).json({ detail: 'Error copiando video de muestra' });
    }
    // Crear registro de video
    let videoId;
    try {
        const r = await pool.query('INSERT INTO videos (usuario_id, original_filename, file_path, transcript) VALUES ($1,$2,$3,$4) RETURNING id', [userId, 'sample.mp4', dest, null]);
        videoId = r.rows[0].id;
    }
    catch (err) {
        console.error('Error insertando video muestra:', err);
        try {
            fs.unlinkSync(dest);
        }
        catch { }
        return res.status(500).json({ detail: 'Error creando video' });
    }
    // Crear job
    let jobId;
    try {
        const r = await pool.query('INSERT INTO jobs (video_id, status, progress) VALUES ($1, $2, $3) RETURNING id', [videoId, 'pending', 0]);
        jobId = r.rows[0].id;
    }
    catch (err) {
        console.error('Error creando job muestra:', err);
        // No borramos el video, queda para reintento
        return res.status(500).json({ detail: 'Error creando job' });
    }
    // Ejecutar job en background (no await)
    runJob(jobId).catch((err) => console.error(`[sample] job ${jobId} falló:`, err));
    // Responder 202 con JobResponse (paridad con FastAPI)
    return res.status(202).json({
        id: jobId,
        video_id: videoId,
        status: 'PENDING',
        progress: 0,
        error_message: null,
        result_metadata: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
    });
});
videosRouter.get('/', authMiddleware, async (req, res) => {
    const userId = req.user.id;
    try {
        const r = await pool.query('SELECT id, original_filename AS filename, created_at FROM videos WHERE usuario_id = $1 ORDER BY created_at DESC', [userId]);
        const items = r.rows.map((row) => ({
            id: row.id,
            filename: row.filename,
            created_at: new Date(row.created_at).toISOString(),
        }));
        return res.json(items);
    }
    catch (err) {
        console.error('GET /videos error', err);
        return res.status(500).json({ detail: 'Error interno' });
    }
});
videosRouter.use((err, _req, res, _next) => {
    const e = err;
    if (e?.code === 'LIMIT_FILE_SIZE')
        return res.status(400).json({ detail: "Archivo supera el tamaño máximo de 500MB" });
    if (e?.message)
        return res.status(400).json({ detail: e.message });
    return res.status(500).json({ detail: 'Error interno' });
});
