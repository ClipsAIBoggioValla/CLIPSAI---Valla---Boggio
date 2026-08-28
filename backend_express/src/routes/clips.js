const express = require('express');
const db = require('../config/database');
const authenticateToken = require('../middleware/auth');

const router = express.Router();

// GET /clips - Listar todos los clips del usuario
router.get('/', authenticateToken, async (req, res) => {
  try {
    const result = await db.query(
      'SELECT * FROM clips WHERE user_id = $1 ORDER BY created_at DESC',
      [req.user.id]
    );
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// GET /clips/video/:video_id - Listar clips pertenecientes a un video en particular
router.get('/video/:video_id', authenticateToken, async (req, res) => {
  try {
    const result = await db.query(
      'SELECT * FROM clips WHERE video_id = $1 AND user_id = $2 ORDER BY start_time ASC',
      [req.params.video_id, req.user.id]
    );
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// GET /clips/:id - Obtener un clip específico por ID
router.get('/:id', authenticateToken, async (req, res) => {
  try {
    const result = await db.query(
      'SELECT * FROM clips WHERE id = $1 AND user_id = $2',
      [req.params.id, req.user.id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ detail: 'Clip not found' });
    }

    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

module.exports = router;