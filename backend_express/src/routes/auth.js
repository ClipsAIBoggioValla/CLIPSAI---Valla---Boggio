const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const db = require('../config/database');
const authenticateToken = require('../middleware/auth');

const router = express.Router();
const SECRET_KEY = process.env.SECRET_KEY || 'tu_clave_secreta_compartida';

// POST /auth/register
router.post('/register', async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ detail: 'Email and password required' });
  }

  try {
    const existing = await db.query('SELECT id FROM users WHERE email = $1', [email]);
    if (existing.rows.length > 0) {
      return res.status(400).json({ detail: 'Email already registered' });
    }

    const hashedPassword = await bcrypt.hash(password, 10);
    const result = await db.query(
      'INSERT INTO users (email, hashed_password, created_at) VALUES ($1, $2, NOW()) RETURNING id, email, created_at',
      [email, hashedPassword]
    );

    res.status(201).json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// POST /auth/token (Soporta JSON y Form Data OAuth2)
router.post('/token', async (req, res) => {
  const email = req.body.username || req.body.email;
  const password = req.body.password;

  if (!email || !password) {
    return res.status(400).json({ detail: 'Incorrect email or password' });
  }

  try {
    const result = await db.query('SELECT * FROM users WHERE email = $1', [email]);
    const user = result.rows[0];

    if (!user || !(await bcrypt.compare(password, user.hashed_password))) {
      return res.status(401).json({ detail: 'Incorrect email or password' });
    }

    const accessToken = jwt.sign({ sub: user.email }, SECRET_KEY, { algorithm: 'HS256', expiresIn: '1d' });

    res.json({ access_token: accessToken, token_type: 'bearer' });
  } catch (err) {
    res.status(500).json({ detail: err.message });
  }
});

// GET /auth/me
router.get('/me', authenticateToken, (req, res) => {
  res.json(req.user);
});

module.exports = router;