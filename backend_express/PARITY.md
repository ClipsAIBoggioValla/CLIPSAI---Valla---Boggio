# Paridad Express ↔ FastAPI (Issue 6)

Este documento compara endpoint por endpoint los dos backends y documenta las
diferencias conocidas. **Objetivo:** un mismo usuario/token puede operar
indistintamente contra cualquiera de los dos backends.

---

## Interoperabilidad de Tokens (JWT)

Ambos backends emiten y validan JWT **HS256** con el mismo esquema:

| Claim | Tipo | Descripción |
|-------|------|-------------|
| `sub` | `string` (UUID) | ID del usuario (formato UUID) |
| `iat` | `datetime` | Fecha de emisión (UTC) |
| `exp` | `datetime` | Fecha de expiración (UTC) |
| `type` | `string` | Siempre `"access"` |

**Requisito para que un mismo token funcione en ambos backends:**
- Ambos leen el secreto de la variable `JWT_SECRET` (el mismo valor).
- Ambos usan `JWT_EXPIRE_MINUTES` (default 60) para la expiración.
- Un token emitido por Express puede ser validado por FastAPI y viceversa,
  siempre que compartan el mismo secreto.

---

## Tabla Comparativa Endpoint por Endpoint

### Salud

| Método | Ruta | FastAPI | Express | Estado |
|--------|------|---------|---------|--------|
| GET | `/health` | ✅ | ✅ | ✅ Paridad |

### Autenticación

| Método | Ruta | FastAPI | Express | Estado |
|--------|------|---------|---------|--------|
| POST | `/auth/registro` | ✅ | ✅ | ✅ Paridad |
| POST | `/auth/login` | ✅ | ✅ | ✅ Paridad |
| POST | `/auth/login/form` | ✅ | ✅ | ✅ Paridad |
| GET | `/auth/me` | ✅ | ✅ | ✅ Paridad |

**Contrato de respuesta (POST /auth/registro):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "created_at": "2026-09-02T12:00:00Z",
  "updated_at": "2026-09-02T12:00:00Z"
}
```

**Contrato de respuesta (POST /auth/login):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### Videos

| Método | Ruta | FastAPI | Express | Estado |
|--------|------|---------|---------|--------|
| POST | `/videos` | ✅ | ✅ | ✅ Paridad |
| GET | `/videos` | ✅ | ✅ | ✅ Paridad |

**Validación de archivos (paridad):**
- Extensiones de video permitidas: `.mp4`, `.mov`, `.avi`
- Extensiones de transcripción permitidas: `.txt`, `.srt`
- Tamaño máximo: 500MB por archivo
- Si falta alguno de los dos archivos → 400

**Respuesta (POST /videos y GET /videos):** `{ id, filename, created_at }`
(no se exponen rutas internas ni contenido de transcripción).

### Jobs

| Método | Ruta | FastAPI | Express | Estado |
|--------|------|---------|---------|--------|
| POST | `/videos/{video_id}/jobs` | ✅ | ✅ | ✅ Paridad |
| GET | `/jobs/{id}` | ✅ | ✅ | ✅ Paridad |

**Nota sobre HTTP Status y estados:**
- `POST /videos/{video_id}/jobs` devuelve **202 Accepted** (procesamiento async)
- El estado se serializa en MAYÚSCULAS: `PENDING → PROCESSING → COMPLETED/FAILED`
- El job finalizado incluye `result_metadata` y `error_message` en caso de fallo

### Clips

| Método | Ruta | FastAPI | Express | Estado |
|--------|------|---------|---------|--------|
| GET | `/clips` | ✅ | ✅ | ✅ Paridad |
| GET | `/clips/{id}` | ✅ | ✅ | ✅ Paridad |
| PATCH | `/clips/{id}` | ✅ | ✅ | ✅ Paridad |
| DELETE | `/clips/{id}` | ✅ | ✅ | ✅ Paridad |
| GET | `/clips/{id}/descarga` | ✅ | ✅ | ✅ Paridad |

**Filtros en GET /clips:**
- `?video_id=...` - Filtrar por video
- `?status=...` - Filtrar por estado

---

## Formato de Errores

Todos los errores siguen el formato FastAPI: `{ "detail": "mensaje" }`.

### Códigos de estado y mensajes (paridad)

| Código | Mensaje | Contexto |
|--------|---------|----------|
| 400 | `"Solicitud invalida"` | Validación genérica |
| 400 | `"Nada para actualizar"` | PATCH /clips sin campos |
| 400 | `"video: extension no permitida '.xx'. Permitidas: ..."` | Extensión inválida |
| 401 | `"Credenciales invalidas"` | Login fallido |
| 401 | `"Token invalido"` | Token corrupto / firma inválida |
| 401 | `"Token expirado"` | Token vencido |
| 401 | `"Usuario no encontrado"` | Usuario no existe en DB |
| 403 | `"No autorizado para este video"` | Job sobre video ajeno |
| 403 | `"No autorizado para este clip"` | Clip de otro usuario |
| 404 | `"No encontrado"` | Recurso no existe |
| 409 | `"El email ya esta registrado"` | Email duplicado |
| 500 | `"Internal Server Error"` | Error genérico del servidor |

**Todas las respuestas 401 incluyen el header `WWW-Authenticate: Bearer`.**

---

## Diferencias Conocidas

1. **Bibliotecas de JWT** - FastAPI usa `python-jose`, Express usa
   `jsonwebtoken`. Ambos emiten tokens HS256 compatibles.

2. **CORS** - FastAPI no instala middleware CORS; Express usa `cors()` para
   permitir clientes web. Es una diferencia de infraestructura intencional.

3. **Timestamps** - FastAPI serializa ISO-8601 con microsegundos; Express usa
   precisión de milisegundos. Ambos son ISO-8601 UTC válidos y los scripts de
   verificación no comparan timestamps.

---

## Verificación

Para probar la interoperabilidad:

```bash
# 1. Iniciar servicios
docker compose up -d

# 2. Registrar usuario (Express)
curl -X POST http://localhost:8001/auth/registro \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# 3. Login (Express) - obtener token
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# 4. Usar el token en FastAPI
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <token>"
```

Si el paso 4 funciona, el mismo token es interoperable entre ambos backends.

Además, los scripts de aceptación (`scripts/verify-auth.sh`,
`scripts/verify-issue4.sh`, `scripts/verify-issue5.sh`) pasan contra Express con
`BASE_URL=http://localhost:8001` de la misma forma que contra FastAPI.
