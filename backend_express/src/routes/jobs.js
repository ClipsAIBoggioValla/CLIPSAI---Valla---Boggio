const express = require('express');
const db = require('../config/database');
const authenticateToken = require('../middleware/auth');
const { runEngineSubprocess } = require('../utils/engineRunner');
const { notFound, forbidden, internalError } = require('../utils/errors');

const router = express.Router();

function parseTimeToSeconds(value) {
  if (value === undefined || value === null) return 0.0;
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0.0;

  if (typeof value === 'string') {
    const str = value.trim();
    if (str === '') return 0.0;

    const parts = str.split(':');
    if (parts.length === 3) {
      const [h, m, s] = parts;
      const seconds = Number(h) * 3600 + Number(m) * 60 + Number(s);
      return Number.isFinite(seconds) ? seconds : 0.0;
    }
    if (parts.length === 2) {
      const [m, s] = parts;
      const seconds = Number(m) * 60 + Number(s);
      return Number.isFinite(seconds) ? seconds : 0.0;
    }
  }

  const num = Number(value);
  return Number.isFinite(num) ? num : 0.0;
}

function toJobResponse(row) {
  return {
    id: row.id,
    video_id: row.video_id,
    status: (row.status || '').toUpperCase(),
    error_message: row.error_message || null,
    result_metadata: row.result_metadata || null,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function extractClips(result) {
  if (result && Array.isArray(result.clips)) return result.clips;
  if (result && Array.isArray(result.result)) return result.result;
  if (result && Array.isArray(result.clips_generated)) return result.clips_generated;
  return [];
}

function buildClipRow(item, jobId, videoId) {
  const title = String(
    item.title || item.titulo || item.titulo_sugerido || item.name || 'Clip',
  ).slice(0, 255);

  const startRaw = item.start_time !== undefined ? item.start_time
    : (item.inicio !== undefined ? item.inicio
      : (item.start !== undefined ? item.start : 0));
  const endRaw = item.end_time !== undefined ? item.end_time
    : (item.fin !== undefined ? item.fin
      : (item.end !== undefined ? item.end : 10));

  let startTime = parseTimeToSeconds(startRaw);
  let endTime = parseTimeToSeconds(endRaw);
  if (endTime <= startTime) endTime = startTime + 30.0;

  const scoreNum = Number(item.score);
  const score = Number.isFinite(scoreNum) && item.score !== null && item.score !== undefined
    ? scoreNum
    : null;

  let tags = null;
  if (Array.isArray(item.tags)) {
    tags = item.tags;
  } else if (item.tags !== null && item.tags !== undefined) {
    tags = [String(item.tags)];
  }

  const storage = String(item.storage_path || item.file_path || item.path || '').trim();

  return [
    videoId,
    jobId,
    title,
    startTime,
    endTime,
    score,
    tags ? JSON.stringify(tags) : null,
    storage,
  ];
}

async function runJob(jobId, video) {
  try {
    await db.query('UPDATE jobs SET status = $1, updated_at = NOW() WHERE id = $2', ['processing', jobId]);

    const result = await runEngineSubprocess(video.file_path, video.transcription_filepath || '');

    const clips = extractClips(result);
    for (const item of clips) {
      const values = buildClipRow(item, jobId, video.id);
      await db.query(
        `INSERT INTO clips (video_id, job_id, title, start_time, end_time, score, tags, file_path, status, created_at, updated_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'ready', NOW(), NOW())`,
        values,
      );
    }

    const metadata = result && typeof result === 'object' ? JSON.stringify(result) : null;
    await db.query(
      'UPDATE jobs SET status = $1, result_metadata = $2, error_message = NULL, updated_at = NOW() WHERE id = $3',
      ['completed', metadata, jobId],
    );
  } catch (err) {
    console.error('Background job processing error:', err);
    const message = String(err.message || err).slice(0, 2000);
    await db.query(
      'UPDATE jobs SET status = $1, error_message = $2, updated_at = NOW() WHERE id = $3',
      ['failed', message, jobId],
    );
  }
}

router.post('/videos/:video_id/jobs', authenticateToken, async (req, res) => {
  const { video_id } = req.params;

  try {
    const videoRes = await db.query('SELECT * FROM videos WHERE id = $1', [video_id]);

    if (videoRes.rows.length === 0) {
      return notFound(res, 'Video no encontrado');
    }

    const video = videoRes.rows[0];

    if (video.usuario_id !== req.user.id) {
      return forbidden(res, 'No autorizado para este video');
    }

    const jobRes = await db.query(
      'INSERT INTO jobs (video_id, status, created_at, updated_at) VALUES ($1, $2, NOW(), NOW()) RETURNING *',
      [video_id, 'pending'],
    );
    const job = jobRes.rows[0];

    setImmediate(() => runJob(job.id, video));

    res.status(202).json(toJobResponse(job));
  } catch (err) {
    console.error('Create job error:', err);
    return internalError(res, err.message);
  }
});

router.get('/jobs/:id', authenticateToken, async (req, res) => {
  try {
    const result = await db.query(
      `SELECT j.* FROM jobs j
       JOIN videos v ON j.video_id = v.id
       WHERE j.id = $1 AND v.usuario_id = $2`,
      [req.params.id, req.user.id],
    );

    if (result.rows.length === 0) {
      return notFound(res, 'Job no encontrado');
    }

    res.json(toJobResponse(result.rows[0]));
  } catch (err) {
    console.error('Get job error:', err);
    return internalError(res, err.message);
  }
});

module.exports = router;
