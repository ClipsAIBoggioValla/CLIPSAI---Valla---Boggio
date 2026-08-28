const express = require('express');
const db = require('../config/database');
const authenticateToken = require('../middleware/auth');
const { runEngineSubprocess } = require('../utils/engineRunner');

const router = express.Router();

// POST /jobs (Crear y procesar Job)
router.post('/', authenticateToken, async (req, res) => {
  const { video_id } = req.body;

  try {
    const videoRes = await db.query('SELECT * FROM videos WHERE id = $1 AND user_id = $2', [video_id, req.user.id]);
    if (videoRes.rows.length === 0) {
      return res.status(404).json({ detail: 'Video not found' });
    }
    const video = videoRes.rows[0];

    // Insertar Job inicial (pending)
    const jobRes = await db.query(
      'INSERT INTO jobs (video_id, user_id, status, created_at) VALUES ($1, $2, $3, NOW()) RETURNING *',
      [video_id, req.user.id, 'pending']
    );
    const job = jobRes.rows[0];

    // Procesar de manera asíncrona (Background Task)
    setImmediate(async () => {
      try {
        await db.query('UPDATE jobs SET status = $1 WHERE id = $2', ['processing', job.id]);

        const result = await runEngineSubprocess(video.filepath, video.transcription_path);

        // Guardar clips detectados
        for (const clip of result.clips || []) {
          await db.query(
            `INSERT INTO clips (video_id, job_id, user_id, start_time, end_time, duration, score, title, hook, criterio, tags, filepath, created_at)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())`,
            [
              video_id,
              job.id,
              req.user.id,
              clip.inicio,
              clip.fin,
              clip.duracion,
              clip.score,
              clip.titulo_sugerido,
              clip.hook_principal,
              clip.criterio_dominante,
              JSON.stringify(clip.tags || []),
              clip.archivo_salida || ''
            ]
          );
        }

        await db.query(
          'UPDATE jobs SET status = $1, result_metadata = $2, updated_at = NOW() WHERE id = $3',
          ['completed', JSON.stringify(result), job.id]
        );
      } catch (err) {
        await db.query(
          'UPDATE jobs SET status = $1, error_message = $2, updated_at = NOW() WHERE id = $3',
          ['failed', err.message, job.id]
        );
      }
    });

    res.status(201).json(job);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// GET /jobs
router.get('/', authenticateToken, async (req, res) => {
  const result = await db.query('SELECT * FROM jobs WHERE user_id = $1 ORDER BY created_at DESC', [req.user.id]);
  res.json(result.rows);
});

// GET /jobs/:id
router.get('/:id', authenticateToken, async (req, res) => {
  const result = await db.query('SELECT * FROM jobs WHERE id = $1 AND user_id = $2', [req.params.id, req.user.id]);
  if (result.rows.length === 0) {
    return res.status(404).json({ detail: 'Job not found' });
  }
  res.json(result.rows[0]);
});

module.exports = router;