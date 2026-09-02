const express = require('express');
const crypto = require('crypto');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const db = require('../config/database');
const authenticateToken = require('../middleware/auth');
const { badRequest, internalError } = require('../utils/errors');

const router = express.Router();

const uploadDir = process.env.UPLOAD_DIR || path.resolve(__dirname, '../../uploads');
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi'];
const ALLOWED_TRANSCRIPT_EXTENSIONS = ['.txt', '.srt'];
const ALLOWED_VIDEO_EXTENSIONS_SORTED = ['.avi', '.mov', '.mp4'];
const ALLOWED_TRANSCRIPT_EXTENSIONS_SORTED = ['.srt', '.txt'];
const MAX_FILE_SIZE = 500 * 1024 * 1024;

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDir),
  filename: (_req, file, cb) => {
    const hex = crypto.randomUUID().replace(/-/g, '');
    const ext = path.extname(file.originalname);
    cb(null, `${hex}${ext}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: MAX_FILE_SIZE },
  fileFilter(req, file, cb) {
    const ext = path.extname(file.originalname).toLowerCase();

    if (file.fieldname === 'video' && !ALLOWED_VIDEO_EXTENSIONS.includes(ext)) {
      const err = new Error(`video: extension no permitida '${ext}'. Permitidas: ${ALLOWED_VIDEO_EXTENSIONS_SORTED.join(', ')}`);
      err.status = 400;
      return cb(err);
    }

    if (file.fieldname === 'transcription' && !ALLOWED_TRANSCRIPT_EXTENSIONS.includes(ext)) {
      const err = new Error(`transcription: extension no permitida '${ext}'. Permitidas: ${ALLOWED_TRANSCRIPT_EXTENSIONS_SORTED.join(', ')}`);
      err.status = 400;
      return cb(err);
    }

    cb(null, true);
  },
});

const uploadFields = upload.fields([
  { name: 'video', maxCount: 1 },
  { name: 'transcription', maxCount: 1 },
]);

function cleanUploadedFiles(files) {
  if (!files) return;

  for (const field of Object.values(files)) {
    for (const file of field) {
      fs.unlink(file.path, () => {});
    }
  }
}

router.post('/', authenticateToken, (req, res, next) => {
  uploadFields(req, res, (err) => {
    if (err) {
      cleanUploadedFiles(req.files);

      if (err.code === 'LIMIT_FILE_SIZE') {
        const fieldName = err.field || 'archivo';
        const originalName = (req.files && req.files[fieldName] && req.files[fieldName][0])
          ? req.files[fieldName][0].originalname
          : fieldName;
        return badRequest(res, `Archivo '${originalName}' supera el tamaño máximo de 500MB`);
      }

      if (err.status === 400 && err.message) {
        return badRequest(res, err.message);
      }

      return internalError(res, err.message || 'Error al procesar archivos');
    }

    next();
  });
}, async (req, res) => {
  try {
    const videoFile = req.files && req.files['video'] ? req.files['video'][0] : null;
    const transcriptionFile = req.files && req.files['transcription'] ? req.files['transcription'][0] : null;

    if (!videoFile) {
      cleanUploadedFiles(req.files);
      return badRequest(res, 'Se requieren ambos archivos: video y transcription');
    }

    if (!transcriptionFile) {
      cleanUploadedFiles(req.files);
      return badRequest(res, 'Se requieren ambos archivos: video y transcription');
    }

    let transcriptContent = null;
    try {
      const data = fs.readFileSync(transcriptionFile.path, 'utf-8');
      transcriptContent = data.substring(0, 50000) || null;
    } catch (readErr) {
      console.warn('Could not read transcript file:', readErr.message);
    }

    const result = await db.query(
      `INSERT INTO videos (usuario_id, original_filename, file_path, transcription_filepath, transcript, created_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
       RETURNING id, original_filename, created_at`,
      [
        req.user.id,
        videoFile.originalname,
        videoFile.path,
        transcriptionFile.path,
        transcriptContent,
      ],
    );

    const row = result.rows[0];
    res.status(201).json({
      id: row.id,
      filename: row.original_filename,
      created_at: row.created_at,
    });
  } catch (err) {
    console.error('Upload error:', err);
    cleanUploadedFiles(req.files);
    return internalError(res, err.message);
  }
});

router.get('/', authenticateToken, async (req, res) => {
  try {
    const result = await db.query(
      'SELECT id, original_filename, created_at FROM videos WHERE usuario_id = $1 ORDER BY created_at DESC',
      [req.user.id],
    );

    res.json(
      result.rows.map((row) => ({
        id: row.id,
        filename: row.original_filename,
        created_at: row.created_at,
      })),
    );
  } catch (err) {
    console.error('List videos error:', err);
    return internalError(res, err.message);
  }
});

module.exports = router;
