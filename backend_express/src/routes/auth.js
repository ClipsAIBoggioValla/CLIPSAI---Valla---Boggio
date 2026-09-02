const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const db = require('../config/database');
const authenticateToken = require('../middleware/auth');
const { badRequest, conflict, internalError, unauthorized } = require('../utils/errors');

const router = express.Router();

const JWT_SECRET = process.env.JWT_SECRET || process.env.SECRET_KEY || 'tu_clave_secreta_compartida';
const JWT_EXPIRE_MINUTES = Number(process.env.JWT_EXPIRE_MINUTES || 60);

function toBcryptInput(value) {
  if (typeof value !== 'string') return '';
  return Buffer.from(value, 'utf8').subarray(0, 72).toString('utf8');
}

function isValidEmail(email) {
  return typeof email === 'string' && email.trim().length > 0 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

router.post('/registro', async (req, res) => {
  const { email, password, full_name } = req.body || {};

  if (!isValidEmail(email) || typeof password !== 'string' || password.length < 8 || password.length > 128) {
    return badRequest(res, 'Solicitud invalida');
  }

  if (full_name !== undefined && full_name !== null && String(full_name).length > 100) {
    return badRequest(res, 'Solicitud invalida');
  }

  try {
    const existing = await db.query('SELECT id FROM usuarios WHERE email = $1', [email]);
    if (existing.rows.length > 0) {
      return conflict(res, 'El email ya esta registrado');
    }

    const hashedPassword = await bcrypt.hash(toBcryptInput(password), 10);
    const result = await db.query(
      `INSERT INTO usuarios (email, hashed_password, full_name, created_at, updated_at)
       VALUES ($1, $2, $3, NOW(), NOW())
       RETURNING id, email, full_name, created_at, updated_at`,
      [email, hashedPassword, full_name || null],
    );

    res.status(201).json(result.rows[0]);
  } catch (err) {
    if (err.code === '23505') {
      return conflict(res, 'El email ya esta registrado');
    }
    console.error('Registration error:', err);
    return internalError(res, err.message);
  }
});

router.post('/login', async (req, res) => {
  const { email, password } = req.body || {};

  if (!email || !password) {
    return badRequest(res, 'Solicitud invalida');
  }

  try {
    const result = await db.query('SELECT * FROM usuarios WHERE email = $1', [email]);
    const user = result.rows[0];

    if (!user || !(await bcrypt.compare(toBcryptInput(password), user.hashed_password))) {
      return unauthorized(res, 'Credenciales invalidas');
    }

    const accessToken = jwt.sign(
      { sub: user.id, type: 'access' },
      JWT_SECRET,
      { algorithm: 'HS256', expiresIn: `${JWT_EXPIRE_MINUTES}m` },
    );

    res.json({ access_token: accessToken, token_type: 'bearer' });
  } catch (err) {
    console.error('Login error:', err);
    return internalError(res, err.message);
  }
});

router.post('/login/form', async (req, res) => {
  const email = req.body.username || req.body.email;
  const { password } = req.body || {};

  if (!email || !password) {
    return badRequest(res, 'Solicitud invalida');
  }

  try {
    const result = await db.query('SELECT * FROM usuarios WHERE email = $1', [email]);
    const user = result.rows[0];

    if (!user || !(await bcrypt.compare(toBcryptInput(password), user.hashed_password))) {
      return unauthorized(res, 'Credenciales invalidas');
    }

    const accessToken = jwt.sign(
      { sub: user.id, type: 'access' },
      JWT_SECRET,
      { algorithm: 'HS256', expiresIn: `${JWT_EXPIRE_MINUTES}m` },
    );

    res.json({ access_token: accessToken, token_type: 'bearer' });
  } catch (err) {
    console.error('Login form error:', err);
    return internalError(res, err.message);
  }
});

router.get('/me', authenticateToken, async (req, res) => {
  try {
    const result = await db.query(
      'SELECT id, email, full_name, created_at, updated_at FROM usuarios WHERE id = $1',
      [req.user.id],
    );

    if (result.rows.length === 0) {
      return unauthorized(res, 'Usuario no encontrado');
    }

    res.json(result.rows[0]);
  } catch (err) {
    console.error('Get user error:', err);
    return internalError(res, err.message);
  }
});

module.exports = router;
