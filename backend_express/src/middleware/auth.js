const jwt = require('jsonwebtoken');
const db = require('../config/database');

const JWT_SECRET = process.env.JWT_SECRET || process.env.SECRET_KEY || 'tu_clave_secreta_compartida';

function sendUnauthorized(res, detail = 'Token invalido') {
  res.setHeader('WWW-Authenticate', 'Bearer');
  return res.status(401).json({ detail });
}

async function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token || !authHeader || !authHeader.toLowerCase().startsWith('bearer ')) {
    return sendUnauthorized(res, 'Token invalido');
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET, { algorithms: ['HS256'] });

    if (!decoded.sub) {
      return sendUnauthorized(res, 'Token invalido');
    }

    const userResult = await db.query(
      'SELECT id, email, full_name, created_at, updated_at FROM usuarios WHERE id = $1',
      [decoded.sub],
    );

    if (userResult.rows.length === 0) {
      return sendUnauthorized(res, 'Usuario no encontrado');
    }

    req.user = userResult.rows[0];
    next();
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      return sendUnauthorized(res, 'Token expirado');
    }

    if (err.name === 'JsonWebTokenError' || err.name === 'NotBeforeError') {
      return sendUnauthorized(res, 'Token invalido');
    }

    console.error('Auth middleware error:', err);
    return sendUnauthorized(res, 'Token invalido');
  }
}

module.exports = authenticateToken;
