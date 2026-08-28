const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const db = require('../config/database');
const authenticateToken = require('../middleware/auth');

const router = express.Router();

// Configuración de almacenamiento para subida de videos
const uploadDir = path.resolve(__dirname, '../../uploads');
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
    const ext = path.extname(file.originalname);
    cb(null, `${file.fieldname}-${uniqueSuffix}${ext}`);
  },
});

const upload = multer({ storage });

// POST /videos/upload - Subir video y opcionalmente transcripción
router.post('/upload', authenticateToken, upload.fields([
  { name: 'video', maxCount: 1 },
  { name: 'transcription', maxCount: 1 }
]), async (req, res) => {
  try {
    const videoFile = req.files && req.files['video'] ? req.files['video'][0] : null;
    const transcriptionFile = req.files && req.files['transcription'] ? req.files['transcription'][0] : null;

    if (!videoFile) {
      return res.status(400).json({ detail: 'Video file is required' });
    }

    const videoPath = videoFile.path;
    const transcriptionPath = transcriptionFile ? transcriptionFile.path : (req.body.transcription_path || '');
    const filename = videoFile.originalname;

    const result = await db.query(
      `INSERT INTO videos (filename, filepath, transcription_path, user_id, created_at)
       VALUES ($1, $2, $3, $4, NOW())
       RETURNING id, filename, filepath, transcription_path, user_id, created_at`,
      [filename, videoPath, transcriptionPath, req.user.id]
    );

    res.status(201).json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// GET /videos - Listar videos del usuario autenticado
router.get('/', authenticateToken, async (req, res) => {
  try {
    const result = await db.query(
      'SELECT id, filename, filepath, transcription_path, user_id, created_at FROM videos WHERE user_id = $1 ORDER BY created_at DESC',
      [req.user.id]
    );
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// GET /videos/:id - Obtener video por ID
router.get('/:id', authenticateToken, async (req, res) => {
  try {
    const result = await db.query(
      'SELECT id, filename, filepath, transcription_path, user_id, created_at FROM videos WHERE id = $1 AND user_id = $2',
      [req.params.id, req.user.id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ detail: 'Video not found' });
    }

    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

module.exports = router;