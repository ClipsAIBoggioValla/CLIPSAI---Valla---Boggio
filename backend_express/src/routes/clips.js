const express = require('express');
const path = require('path');
const os = require('os');
const fs = require('fs');
const db = require('../config/database');
const authenticateToken = require('../middleware/auth');
const { notFound, forbidden, badRequest, internalError } = require('../utils/errors');

const router = express.Router();

async function resolveClip(clipId) {
  const result = await db.query(
    `SELECT c.*, j.video_id AS job_video_id
     FROM clips c
     JOIN jobs j ON c.job_id = j.id
     WHERE c.id = $1`,
    [clipId],
  );
  return result.rows[0] || null;
}

async function assertOwnership(clip, userId) {
  let videoId = clip.video_id || clip.job_video_id;

  let video = null;
  if (videoId) {
    const videoRes = await db.query('SELECT id, usuario_id FROM videos WHERE id = $1', [videoId]);
    if (videoRes.rows.length > 0) {
      video = videoRes.rows[0];
    }
  }

  if (!video) {
    return { status: 404, detail: 'Clip no encontrado' };
  }

  if (video.usuario_id !== userId) {
    return { status: 403, detail: 'No autorizado para este clip' };
  }

  return { status: 200 };
}

function toClipResponse(row) {
  return {
    id: row.id,
    video_id: row.video_id || row.job_video_id || null,
    job_id: row.job_id,
    title: row.title,
    start_time: row.start_time,
    end_time: row.end_time,
    score: row.score,
    tags: row.tags,
    storage_path: row.file_path,
    status: row.status,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

router.get('/', authenticateToken, async (req, res) => {
  try {
    const { video_id, status } = req.query;

    let query = `
      SELECT c.*, j.video_id AS job_video_id
      FROM clips c
      JOIN jobs j ON c.job_id = j.id
      JOIN videos v ON j.video_id = v.id
      WHERE v.usuario_id = $1
    `;
    const params = [req.user.id];
    let paramIndex = 2;

    if (video_id) {
      query += ` AND j.video_id = $${paramIndex}`;
      params.push(video_id);
      paramIndex++;
    }

    if (status) {
      query += ` AND c.status = $${paramIndex}`;
      params.push(status);
      paramIndex++;
    }

    query += ' ORDER BY c.created_at DESC';

    const result = await db.query(query, params);
    res.json(result.rows.map(toClipResponse));
  } catch (err) {
    console.error('List clips error:', err);
    return internalError(res, err.message);
  }
});

router.get('/:id', authenticateToken, async (req, res) => {
  try {
    const clip = await resolveClip(req.params.id);

    if (!clip) {
      return notFound(res, 'Clip no encontrado');
    }

    const auth = await assertOwnership(clip, req.user.id);
    if (auth.status !== 200) {
      return res.status(auth.status).json({ detail: auth.detail });
    }

    res.json(toClipResponse(clip));
  } catch (err) {
    console.error('Get clip error:', err);
    return internalError(res, err.message);
  }
});

router.patch('/:id', authenticateToken, async (req, res) => {
  try {
    const clip = await resolveClip(req.params.id);

    if (!clip) {
      return notFound(res, 'Clip no encontrado');
    }

    const auth = await assertOwnership(clip, req.user.id);
    if (auth.status !== 200) {
      return res.status(auth.status).json({ detail: auth.detail });
    }

    const { title, tags } = req.body || {};

    if (title === undefined && tags === undefined) {
      return badRequest(res, 'Nada para actualizar');
    }

    const updates = [];
    const params = [];
    let paramIndex = 1;

    if (title !== undefined) {
      updates.push(`title = $${paramIndex}`);
      params.push(title);
      paramIndex++;
    }

    if (tags !== undefined) {
      updates.push(`tags = $${paramIndex}`);
      params.push(JSON.stringify(tags));
      paramIndex++;
    }

    updates.push('updated_at = NOW()');
    params.push(req.params.id);

    const result = await db.query(
      `UPDATE clips SET ${updates.join(', ')} WHERE id = $${paramIndex} RETURNING *`,
      params,
    );

    if (result.rows.length === 0) {
      return notFound(res, 'Clip no encontrado');
    }

    res.json(toClipResponse(result.rows[0]));
  } catch (err) {
    console.error('Update clip error:', err);
    return internalError(res, err.message);
  }
});

router.delete('/:id', authenticateToken, async (req, res) => {
  try {
    const clip = await resolveClip(req.params.id);

    if (!clip) {
      return notFound(res, 'Clip no encontrado');
    }

    const auth = await assertOwnership(clip, req.user.id);
    if (auth.status !== 200) {
      return res.status(auth.status).json({ detail: auth.detail });
    }

    const filePath = clip.file_path || clip.storage_path;
    if (filePath && fs.existsSync(filePath)) {
      try {
        fs.unlinkSync(filePath);
      } catch (fileErr) {
        console.warn('Could not delete clip file:', fileErr.message);
      }
    }

    await db.query('DELETE FROM clips WHERE id = $1', [req.params.id]);

    res.status(204).send();
  } catch (err) {
    console.error('Delete clip error:', err);
    return internalError(res, err.message);
  }
});

router.get('/:id/descarga', authenticateToken, async (req, res) => {
  try {
    const clip = await resolveClip(req.params.id);

    if (!clip) {
      return notFound(res, 'Clip no encontrado');
    }

    const auth = await assertOwnership(clip, req.user.id);
    if (auth.status !== 200) {
      return res.status(auth.status).json({ detail: auth.detail });
    }

    const candidates = [];

    if (clip.file_path) candidates.push(clip.file_path);
    if (clip.storage_path) candidates.push(clip.storage_path);

    const videoId = clip.video_id || clip.job_video_id;
    if (videoId) {
      const videoRes = await db.query(
        'SELECT file_path, transcription_filepath FROM videos WHERE id = $1',
        [videoId],
      );
      if (videoRes.rows.length > 0) {
        const video = videoRes.rows[0];
        if (video.file_path) candidates.push(video.file_path);
        if (video.transcription_filepath) candidates.push(video.transcription_filepath);
      }
    }

    for (const filePath of candidates) {
      if (filePath && fs.existsSync(filePath)) {
        const ext = path.extname(filePath).toLowerCase();
        let mediaType = 'application/octet-stream';

        if (['.mp4', '.mov', '.avi', '.mkv'].includes(ext)) {
          mediaType = 'video/mp4';
        } else if (['.txt', '.srt', '.vtt'].includes(ext)) {
          mediaType = 'text/plain';
        }

        return res.download(filePath, path.basename(filePath), { contentType: mediaType });
      }
    }

    const tmp = path.join(os.tmpdir(), `clip_${clip.id}.txt`);
    try {
      fs.writeFileSync(
        tmp,
        `Clip ${clip.id}\nTitle: ${clip.title || ''}\nStart: ${clip.start_time}\nEnd: ${clip.end_time}\nStatus: ${clip.status}\n`,
        'utf-8',
      );
      return res.download(tmp, `${clip.id}.txt`, { contentType: 'text/plain' });
    } catch (writeErr) {
      return notFound(res, 'Archivo del clip no encontrado');
    }
  } catch (err) {
    console.error('Download clip error:', err);
    return internalError(res, err.message);
  }
});

module.exports = router;
