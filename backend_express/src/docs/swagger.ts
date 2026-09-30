import swaggerJSDoc from 'swagger-jsdoc'

const PORT = Number(process.env.PORT ?? process.env.BACKEND_EXPRESS_PORT ?? 3001)

const swaggerDefinition = {
  openapi: '3.0.0',
  info: {
    title: 'ClipsAI Express API',
    version: '1.0.0',
    description:
      'Backend Express de ClipsAI — paridad con FastAPI (Issue 30). ' +
      'Autenticación JWT, videos/jobs, clips, exportación, métricas y publicación. ' +
      'Servidor espejo contra la misma PostgreSQL dockerizada.',
    contact: { name: 'ClipsAI', url: 'https://api.clipsai.xyz' },
  },
  servers: [
    { url: `http://localhost:${PORT}`, description: 'Local Express' },
    { url: 'http://localhost:8000', description: 'FastAPI referencia' },
    { url: 'https://api.clipsai.xyz', description: 'Producción (Cloudflare Tunnel)' },
  ],
  tags: [
    { name: 'infra', description: 'Healthcheck' },
    { name: 'auth', description: 'Registro y login JWT' },
    { name: 'videos', description: 'Subida y listado de videos' },
    { name: 'jobs', description: 'Jobs asíncronos pendiente → processing → completed' },
    { name: 'clips', description: 'Biblioteca, CRUD y descarga' },
    { name: 'export', description: 'Exportación CSV/JSON' },
    { name: 'metrics', description: 'Métricas 7 días' },
    { name: 'stats', description: 'Resumen dashboard' },
    { name: 'users', description: 'Perfil y preferencias' },
    { name: 'publish', description: 'Publicación a redes' },
  ],
  components: {
    securitySchemes: {
      bearerAuth: { type: 'http', scheme: 'bearer', bearerFormat: 'JWT', description: 'JWT HS256 (Authorization: Bearer <token>)' },
    },
    schemas: {
      UsuarioCreate: {
        type: 'object',
        required: ['email', 'password'],
        properties: {
          email: { type: 'string', format: 'email', example: 'test@clipsai.com' },
          password: { type: 'string', minLength: 8, maxLength: 128, example: 'Test12345!' },
          full_name: { type: 'string', nullable: true, maxLength: 100, example: 'Ada Lovelace' },
        },
      },
      UsuarioRead: {
        type: 'object',
        properties: {
          id: { type: 'string', format: 'uuid' },
          email: { type: 'string', format: 'email' },
          full_name: { type: 'string', nullable: true },
          created_at: { type: 'string', format: 'date-time' },
          updated_at: { type: 'string', format: 'date-time' },
        },
      },
      Token: {
        type: 'object',
        properties: {
          access_token: { type: 'string', example: 'eyJhbGciOiJIUzI1NiJ9...' },
          token_type: { type: 'string', example: 'bearer' },
        },
      },
      VideoResponse: {
        type: 'object',
        properties: {
          id: { type: 'string', format: 'uuid' },
          filename: { type: 'string', example: 'river.mp4' },
          created_at: { type: 'string', format: 'date-time' },
        },
      },
      JobResponse: {
        type: 'object',
        properties: {
          id: { type: 'string', format: 'uuid' },
          video_id: { type: 'string', format: 'uuid' },
          status: { type: 'string', enum: ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'], example: 'COMPLETED' },
          error_message: { type: 'string', nullable: true },
          result_metadata: {
            type: 'object',
            nullable: true,
            properties: {
              clips: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    titulo: { type: 'string' },
                    inicio: { type: 'string', example: '00:00:10' },
                    fin: { type: 'string', example: '00:00:45' },
                    score: { type: 'number', example: 7.5 },
                  },
                },
              },
            },
          },
          created_at: { type: 'string', format: 'date-time' },
          updated_at: { type: 'string', format: 'date-time' },
        },
      },
      ClipListItem: {
        type: 'object',
        properties: {
          id: { type: 'string', format: 'uuid' },
          job_id: { type: 'string', format: 'uuid' },
          title: { type: 'string', nullable: true },
          score: { type: 'number', nullable: true },
          start_time: { type: 'number' },
          end_time: { type: 'number' },
          transcript: { type: 'string', nullable: true, description: 'Extracto (máx. 500 chars) de la transcripción del video origen' },
          status: { type: 'string', nullable: true, example: 'ready' },
          published_platform: { type: 'string', nullable: true, example: 'tiktok' },
          social_post_url: { type: 'string', nullable: true },
          published_at: { type: 'string', format: 'date-time', nullable: true },
          created_at: { type: 'string', format: 'date-time' },
        },
      },
      ClipListResponse: {
        type: 'object',
        properties: {
          items: { type: 'array', items: { $ref: '#/components/schemas/ClipListItem' } },
          total: { type: 'integer', example: 25 },
          page: { type: 'integer', example: 1 },
          limit: { type: 'integer', example: 10 },
          total_pages: { type: 'integer', example: 3 },
        },
      },
      ClipResponse: {
        type: 'object',
        properties: {
          id: { type: 'string', format: 'uuid' },
          video_id: { type: 'string', format: 'uuid' },
          job_id: { type: 'string', format: 'uuid' },
          title: { type: 'string', nullable: true },
          score: { type: 'number', nullable: true },
          start_time: { type: 'number' },
          end_time: { type: 'number' },
          tags: { type: 'array', items: { type: 'string' }, nullable: true },
          storage_path: { type: 'string', description: 'Ruta en disco del archivo del clip' },
          status: { type: 'string', example: 'ready' },
          published_platform: { type: 'string', nullable: true },
          social_post_id: { type: 'string', nullable: true },
          social_post_url: { type: 'string', nullable: true },
          published_at: { type: 'string', format: 'date-time', nullable: true },
          publication_status: { type: 'string', nullable: true, example: 'PUBLISHED' },
          social_network: { type: 'string', nullable: true },
          created_at: { type: 'string', format: 'date-time' },
          updated_at: { type: 'string', format: 'date-time' },
        },
      },
      RetrimRequest: {
        type: 'object',
        required: ['start_time', 'end_time'],
        properties: {
          start_time: { type: 'number', minimum: 0, example: 10 },
          end_time: { type: 'number', exclusiveMinimum: 5, example: 45, description: 'Debe ser > start_time. Duración resultante entre 5 y 90 segundos.' },
        },
      },
      RetrimResponse: {
        type: 'object',
        properties: {
          clip_id: { type: 'string', format: 'uuid' },
          start_time: { type: 'number' },
          end_time: { type: 'number' },
          duration: { type: 'number', description: 'end_time - start_time' },
          status: { type: 'string' },
          file_path: { type: 'string', description: 'Ruta del nuevo archivo generado por FFmpeg' },
        },
      },
      JobStreamEvent: {
        type: 'object',
        description: 'Evento SSE emitido en cada cambio de estado del job',
        properties: {
          progress: { type: 'integer', example: 55 },
          status: { type: 'string', enum: ['pending', 'scoring', 'completed', 'failed'] },
          message: { type: 'string', example: 'Procesando con IA' },
          job_id: { type: 'string', format: 'uuid' },
          error: { type: 'string', nullable: true, description: 'Presente solo si el job falló' },
        },
      },
      StatsSummaryResponse: {
        type: 'object',
        properties: {
          total_videos: { type: 'integer' },
          total_clips: { type: 'integer' },
          avg_score: { type: 'number', nullable: true },
          estimated_time_saved_minutes: { type: 'integer' },
          score_distribution: { type: 'object' },
          recent_job: { type: 'object', nullable: true },
        },
      },
      MetricsResponse: {
        type: 'object',
        properties: {
          total_jobs: { type: 'integer' },
          total_clips: { type: 'integer' },
          total_minutes_processed: { type: 'number' },
          time_saved_hours: { type: 'number' },
          platform_distribution: { type: 'object' },
          recent_activity: { type: 'array', items: { type: 'object' } },
        },
      },
      PublishClipRequest: {
        type: 'object',
        required: ['platform'],
        properties: {
          platform: { type: 'string', enum: ['tiktok', 'instagram', 'youtube', 'webhook'], example: 'tiktok' },
          caption: { type: 'string', nullable: true, maxLength: 500, example: '¡River! #RiverPlate' },
          webhook_override_url: { type: 'string', format: 'uri', nullable: true },
        },
      },
      Error: { type: 'object', properties: { detail: { type: 'string' } } },
    },
  },
  security: [{ bearerAuth: [] }],
  paths: {
    '/health': {
      get: {
        tags: ['infra'],
        summary: 'Healthcheck simple',
        security: [],
        responses: { '200': { description: 'ok', content: { 'application/json': { schema: { type: 'object', properties: { status: { type: 'string', example: 'ok' } } } } } } },
      },
    },
    '/auth/registro': {
      post: {
        tags: ['auth'],
        summary: 'Registro de usuario',
        security: [],
        requestBody: { required: true, content: { 'application/json': { schema: { $ref: '#/components/schemas/UsuarioCreate' } } } },
        responses: {
          '201': { description: 'Creado', content: { 'application/json': { schema: { $ref: '#/components/schemas/UsuarioRead' } } } },
          '409': { description: 'Email ya registrado', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '422': { description: 'Validación', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/auth/login': {
      post: {
        tags: ['auth'],
        summary: 'Login JSON',
        security: [],
        requestBody: { required: true, content: { 'application/json': { schema: { type: 'object', required: ['email', 'password'], properties: { email: { type: 'string', format: 'email' }, password: { type: 'string' } } } } } },
        responses: {
          '200': { description: 'Token', content: { 'application/json': { schema: { $ref: '#/components/schemas/Token' } } } },
          '401': { description: 'Credenciales inválidas', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/auth/login/form': {
      post: {
        tags: ['auth'],
        summary: 'Login OAuth2 form (Swagger Authorize)',
        security: [],
        requestBody: { required: true, content: { 'application/x-www-form-urlencoded': { schema: { type: 'object', required: ['username', 'password'], properties: { username: { type: 'string', description: 'email' }, password: { type: 'string' } } } } } },
        responses: { '200': { description: 'Token', content: { 'application/json': { schema: { $ref: '#/components/schemas/Token' } } } } },
      },
    },
    '/auth/me': {
      get: {
        tags: ['auth'],
        summary: 'Perfil autenticado',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'Usuario', content: { 'application/json': { schema: { $ref: '#/components/schemas/UsuarioRead' } } } }, '401': { description: 'No autorizado', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } } },
      },
    },
    '/registro': {
      post: {
        tags: ['auth'],
        deprecated: true,
        summary: 'Registro de usuario (alias raíz)',
        description: 'Alias de `POST /auth/registro`. El router de auth también se monta en `/`. Se mantiene por compatibilidad con clientes v1.',
        security: [],
        requestBody: { required: true, content: { 'application/json': { schema: { $ref: '#/components/schemas/UsuarioCreate' } } } },
        responses: {
          '201': { description: 'Creado', content: { 'application/json': { schema: { $ref: '#/components/schemas/UsuarioRead' } } } },
          '409': { description: 'Email ya registrado', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '422': { description: 'Validación', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/login': {
      post: {
        tags: ['auth'],
        deprecated: true,
        summary: 'Login JSON (alias raíz)',
        description: 'Alias de `POST /auth/login`.',
        security: [],
        requestBody: { required: true, content: { 'application/json': { schema: { type: 'object', required: ['email', 'password'], properties: { email: { type: 'string', format: 'email' }, password: { type: 'string' } } } } } },
        responses: {
          '200': { description: 'Token', content: { 'application/json': { schema: { $ref: '#/components/schemas/Token' } } } },
          '401': { description: 'Credenciales inválidas', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/login/form': {
      post: {
        tags: ['auth'],
        deprecated: true,
        summary: 'Login OAuth2 form (alias raíz)',
        description: 'Alias de `POST /auth/login/form`.',
        security: [],
        requestBody: { required: true, content: { 'application/x-www-form-urlencoded': { schema: { type: 'object', required: ['username', 'password'], properties: { username: { type: 'string', description: 'email' }, password: { type: 'string' } } } } } },
        responses: { '200': { description: 'Token', content: { 'application/json': { schema: { $ref: '#/components/schemas/Token' } } } } },
      },
    },
    '/me': {
      get: {
        tags: ['auth'],
        deprecated: true,
        summary: 'Perfil autenticado (alias raíz)',
        description: 'Alias de `GET /auth/me`.',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'Usuario', content: { 'application/json': { schema: { $ref: '#/components/schemas/UsuarioRead' } } } } },
      },
    },
    '/videos': {
      post: {
        tags: ['videos'],
        summary: 'Subir video y transcripción (multipart)',
        security: [{ bearerAuth: [] }],
        requestBody: {
          required: true,
          content: {
            'multipart/form-data': {
              schema: {
                type: 'object',
                required: ['video', 'transcription'],
                properties: {
                  video: { type: 'string', format: 'binary', description: '.mp4/.mov/.avi ≤500MB' },
                  transcription: { type: 'string', format: 'binary', description: '.txt/.srt' },
                },
              },
            },
          },
        },
        responses: {
          '201': { description: 'Video creado', content: { 'application/json': { schema: { $ref: '#/components/schemas/VideoResponse' } } } },
          '400': { description: 'Formato inválido', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
      get: {
        tags: ['videos'],
        summary: 'Listar videos del usuario',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'Lista', content: { 'application/json': { schema: { type: 'array', items: { $ref: '#/components/schemas/VideoResponse' } } } } } },
      },
    },
    '/videos/{videoId}/jobs': {
      post: {
        tags: ['jobs'],
        summary: 'Crear Job de procesamiento para un video',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'videoId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        responses: {
          '202': { description: 'Job creado (pending)', content: { 'application/json': { schema: { $ref: '#/components/schemas/JobResponse' } } } },
          '404': { description: 'Video no encontrado', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/jobs/{jobId}': {
      get: {
        tags: ['jobs'],
        summary: 'Consultar estado de un Job',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'jobId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        responses: { '200': { description: 'Job', content: { 'application/json': { schema: { $ref: '#/components/schemas/JobResponse' } } } } },
      },
    },
    '/clips': {
      get: {
        tags: ['clips'],
        summary: 'Listar clips del usuario (biblioteca con búsqueda, filtros y paginación)',
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: 'q', in: 'query', schema: { type: 'string' }, description: 'Búsqueda por título o transcripción' },
          { name: 'min_score', in: 'query', schema: { type: 'number', minimum: 0, maximum: 100 } },
          { name: 'sort_by', in: 'query', schema: { type: 'string', enum: ['created_at_desc', 'created_at_asc', 'score_desc', 'score_asc'] } },
          { name: 'page', in: 'query', schema: { type: 'integer', minimum: 1, default: 1 } },
          { name: 'limit', in: 'query', schema: { type: 'integer', minimum: 1, maximum: 100, default: 10 } },
          { name: 'video_id', in: 'query', schema: { type: 'string', format: 'uuid' } },
          { name: 'status', in: 'query', schema: { type: 'string' } },
        ],
        responses: { '200': { description: 'Paginado', content: { 'application/json': { schema: { $ref: '#/components/schemas/ClipListResponse' } } } } },
      },
    },
    '/clips/{clipId}': {
      get: {
        tags: ['clips'],
        summary: 'Obtener un clip por id',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'clipId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        responses: { '200': { description: 'Clip', content: { 'application/json': { schema: { $ref: '#/components/schemas/ClipResponse' } } } } },
      },
      patch: {
        tags: ['clips'],
        summary: 'Actualizar metadata de un clip (title/tags)',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'clipId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        requestBody: { required: true, content: { 'application/json': { schema: { type: 'object', properties: { title: { type: 'string' }, tags: { type: 'array', items: { type: 'string' } } } } } } },
        responses: { '200': { description: 'Actualizado', content: { 'application/json': { schema: { $ref: '#/components/schemas/ClipResponse' } } } } },
      },
      delete: {
        tags: ['clips'],
        summary: 'Eliminar un clip',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'clipId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        responses: { '204': { description: 'Eliminado' } },
      },
    },
    '/clips/{clipId}/descarga': {
      get: {
        tags: ['clips'],
        summary: 'Descargar archivo del clip',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'clipId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        responses: { '200': { description: 'video/mp4', content: { 'video/mp4': { schema: { type: 'string', format: 'binary' } } } } },
      },
    },
    '/clips/{clipId}/retrim': {
      post: {
        tags: ['clips'],
        summary: 'Re-trim del clip con FFmpeg',
        description:
          'Recorta el clip a un nuevo rango [start_time, end_time) usando FFmpeg, guarda el archivo generado ' +
          'en `storage/retrims/` y actualiza `start_time`, `end_time` y `file_path` del clip. ' +
          'La duración resultante debe estar entre 5 y 90 segundos.',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'clipId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        requestBody: { required: true, content: { 'application/json': { schema: { $ref: '#/components/schemas/RetrimRequest' } } } },
        responses: {
          '200': { description: 'Clip re-trimado', content: { 'application/json': { schema: { $ref: '#/components/schemas/RetrimResponse' } } } },
          '404': { description: 'Clip no encontrado o video origen no disponible', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '422': { description: 'Rango inválido (end_time <= start_time, duración <5s o >90s)', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '500': { description: 'FFmpeg falló o no produjo archivo', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/clips/{clipId}/publicar': {
      post: {
        tags: ['publish'],
        summary: 'Publicar clip en red social (async)',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'clipId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        requestBody: { required: true, content: { 'application/json': { schema: { $ref: '#/components/schemas/PublishClipRequest' } } } },
        responses: { '202': { description: 'Encolado PUBLISHING' }, '422': { description: 'platform inválida' } },
      },
    },
    '/jobs/{jobId}/stream': {
      get: {
        tags: ['jobs'],
        summary: 'SSE stream del estado de un Job',
        description:
          'Server-Sent Events que emite un evento en cada cambio de estado del job (cada ~1s). ' +
          'Cierra con `event: done` al llegar a `completed`/`failed`, o con `event: error` si el job no existe o no pertenece al usuario. ' +
          'Requiere un cliente SSE: Swagger UI no puede consumirlo.',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'jobId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        responses: {
          '200': {
            description: 'Stream SSE de progreso',
            content: { 'text/event-stream': { schema: { $ref: '#/components/schemas/JobStreamEvent' } } },
          },
          '422': { description: 'job_id debe ser UUID válido', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/jobs/{jobId}/export': {
      get: {
        tags: ['export'],
        summary: 'Exportar clips de un Job (csv|json)',
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: 'jobId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } },
          { name: 'format', in: 'query', schema: { type: 'string', enum: ['csv', 'json'], default: 'json' } },
        ],
        responses: { '200': { description: 'Archivo' } },
      },
    },
    '/clips/export': {
      get: {
        tags: ['export'],
        summary: 'Exportar biblioteca (csv|json)',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'format', in: 'query', schema: { type: 'string', enum: ['csv', 'json'], default: 'json' } }],
        responses: { '200': { description: 'Archivo' } },
      },
    },
    '/clips/{clipId}/publish': {
      post: {
        tags: ['publish'],
        deprecated: true,
        summary: 'Publicar clip (alias en inglés)',
        description: 'Alias en inglés de `POST /clips/{clipId}/publicar`. Mismo body y mismo comportamiento. Se mantiene por compatibilidad con clientes v1.',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'clipId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        requestBody: { required: true, content: { 'application/json': { schema: { $ref: '#/components/schemas/PublishClipRequest' } } } },
        responses: {
          '202': { description: 'Encolado PUBLISHING' },
          '422': { description: 'platform inválida', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/metrics': {
      get: {
        tags: ['metrics'],
        summary: 'Métricas 7 días',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'Metrics', content: { 'application/json': { schema: { $ref: '#/components/schemas/MetricsResponse' } } } } },
      },
    },
    '/api/metrics': {
      get: {
        tags: ['metrics'],
        deprecated: true,
        summary: 'Métricas 7 días (alias /api)',
        description: 'Alias de `GET /metrics`. Se mantiene por compatibilidad con el prefijo `/api` de FastAPI.',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'Metrics', content: { 'application/json': { schema: { $ref: '#/components/schemas/MetricsResponse' } } } } },
      },
    },
    '/api/v1/jobs/{jobId}/export': {
      get: {
        tags: ['export'],
        deprecated: true,
        summary: 'Exportar clips de un Job (alias /api/v1)',
        description: 'Alias de `GET /jobs/{jobId}/export`. Se mantiene por compatibilidad con el prefijo `/api/v1`.',
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: 'jobId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } },
          { name: 'format', in: 'query', schema: { type: 'string', enum: ['csv', 'json'], default: 'json' } },
        ],
        responses: { '200': { description: 'Archivo' } },
      },
    },
    '/stats/summary': {
      get: {
        tags: ['stats'],
        summary: 'Resumen dashboard',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'Stats', content: { 'application/json': { schema: { $ref: '#/components/schemas/StatsSummaryResponse' } } } } },
      },
    },
    '/users/me': {
      get: {
        tags: ['users'],
        summary: 'Perfil actual',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'User', content: { 'application/json': { schema: { $ref: '#/components/schemas/UsuarioRead' } } } } },
      },
      put: {
        tags: ['users'],
        summary: 'Actualizar perfil',
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { 'application/json': { schema: { type: 'object', properties: { email: { type: 'string', format: 'email' }, full_name: { type: 'string' }, avatar_url: { type: 'string' }, theme_preference: { type: 'string', enum: ['light', 'dark'] } } } } } },
        responses: { '200': { description: 'Actualizado' } },
      },
      patch: {
        tags: ['users'],
        summary: 'Actualizar parcial',
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { 'application/json': { schema: { type: 'object', properties: { email: { type: 'string' }, full_name: { type: 'string' } } } } } },
        responses: { '200': { description: 'Actualizado' } },
      },
    },
    '/users/me/change-password': {
      post: {
        tags: ['users'],
        summary: 'Cambiar contraseña',
        description: 'Verifica la contraseña actual y la reemplaza por `new_password` (8-128 caracteres, distinta de la actual).',
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { 'application/json': { schema: { type: 'object', required: ['current_password', 'new_password'], properties: { current_password: { type: 'string' }, new_password: { type: 'string', minLength: 8, maxLength: 128 } } } } } },
        responses: {
          '200': { description: 'Contraseña actualizada' },
          '400': { description: 'Contraseña actual incorrecta o nueva igual a la actual', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '422': { description: 'Falta current_password/new_password o longitud inválida', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/users/me/password': {
      put: {
        tags: ['users'],
        summary: 'Cambiar contraseña (alias PUT)',
        description: 'Alias en `PUT` de `POST /users/me/change-password`. Mismo body y mismo comportamiento.',
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { 'application/json': { schema: { type: 'object', required: ['current_password', 'new_password'], properties: { current_password: { type: 'string' }, new_password: { type: 'string', minLength: 8, maxLength: 128 } } } } } },
        responses: {
          '200': { description: 'Contraseña actualizada' },
          '400': { description: 'Contraseña actual incorrecta o nueva igual a la actual', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '422': { description: 'Falta current_password/new_password o longitud inválida', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
  },
} as const

const options = {
  definition: swaggerDefinition,
  apis: ['./src/routes/*.ts', './src/controllers/*.ts'],
}

export const swaggerSpec = swaggerJSDoc(options as never)

export const swaggerUiOptions = {
  customCss: '.swagger-ui .topbar { display: none }',
  customSiteTitle: 'ClipsAI Express — Swagger UI',
  swaggerOptions: { persistAuthorization: true },
}
