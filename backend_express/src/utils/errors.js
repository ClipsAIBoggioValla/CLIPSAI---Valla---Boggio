/**
 * Error handling helpers - standardized responses matching FastAPI format
 * All 401 responses include WWW-Authenticate: Bearer header
 */

/**
 * 401 Unauthorized - Token missing, invalid, or expired
 */
function unauthorized(res, detail = 'Token invalido') {
  return res.status(401).json({ detail }).set('WWW-Authenticate', 'Bearer');
}

/**
 * 403 Forbidden - Authenticated but not authorized
 */
function forbidden(res, detail = 'No autorizado para este recurso') {
  return res.status(403).json({ detail });
}

/**
 * 404 Not Found - Resource doesn't exist
 */
function notFound(res, detail = 'No encontrado') {
  return res.status(404).json({ detail });
}

/**
 * 400 Bad Request - Invalid input
 */
function badRequest(res, detail = 'Solicitud invalida') {
  return res.status(400).json({ detail });
}

/**
 * 409 Conflict - Resource already exists (e.g., duplicate email)
 */
function conflict(res, detail = 'El recurso ya existe') {
  return res.status(409).json({ detail });
}

/**
 * 422 Unprocessable Entity - Validation error
 */
function validationError(res, detail = 'Error de validacion') {
  return res.status(422).json({ detail });
}

/**
 * 500 Internal Server Error
 */
function internalError(res, detail = 'Error interno del servidor') {
  return res.status(500).json({ detail });
}

module.exports = {
  unauthorized,
  forbidden,
  notFound,
  badRequest,
  conflict,
  validationError,
  internalError,
};
