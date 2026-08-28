const jwt = require('jsonwebtoken');
const db = require('../config/database');

const SECRET_KEY = process.env.SECRET_KEY || 'tu_clave_secreta_compartida';

async function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1]; // Bearer TOKEN

  if (!token) {
    return res.status(401).json({ detail: 'Not authenticated' });
  }

  try {
    const decoded = jwt.verify(token, SECRET_KEY, { algorithms: ['HS256'] });
    const userResult = await db.query('SELECT id, email FROM users WHERE email = $1', [decoded.sub]);

    if (userResult.rows.length === 0) {
      return res.status(401).json({ detail: 'User not found' });
    }

    req.user = userResult.rows[0];
    next();
  } catch (err) {
    return res.status(401).json({ detail: 'Could not validate credentials' });
  }
}

module.exports = authenticateToken;