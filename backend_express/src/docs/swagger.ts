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
    { name: 'auth-compat', description: 'Alias de login/registro en la raíz' },
    { name: 'videos', description: 'Subida y listado de videos' },
    { name: 'jobs', description: 'Jobs asíncronos pendiente → processing → completed' },
    { name: 'clips', description: 'Biblioteca, CRUD y descarga' },
    { name: 'export', description: 'Exportación CSV/JSON' },
    { name: 'metrics', description: 'Métricas 7 días' },
    { name: 'stats', description: 'Resumen dashboard' },
    { name: 'users', description: 'Perfil y preferencias' },
    { name: 'publish', description: 'Publicación a redes' },
    { name: 'social', description: 'Integraciones OAuth2 (YouTube, Instagram, TikTok)' },
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
          file_path: { type: 'string', nullable: true, example: '/app/storage/clips/abc.mp4' },
          stream_url: { type: 'string', example: '/clips/abc/descarga' },
          duration: { type: 'number', nullable: true, example: 17.5 },
          has_ass: { type: 'boolean', example: true },
          has_hook: { type: 'boolean', example: true },
          tags: { type: 'object', nullable: true },
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
          video_id: { type: 'string', format: 'uuid', nullable: true },
          job_id: { type: 'string', format: 'uuid' },
          title: { type: 'string', nullable: true },
          score: { type: 'number', nullable: true },
          start_time: { type: 'number' },
          end_time: { type: 'number' },
          status: { type: 'string' },
          tags: { type: 'object', nullable: true },
          storage_path: { type: 'string', nullable: true },
          file_path: { type: 'string', nullable: true },
          stream_url: { type: 'string', nullable: true },
          duration: { type: 'number', nullable: true },
          has_ass: { type: 'boolean' },
          has_hook: { type: 'boolean' },
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
      SocialStatus: {
        type: 'object',
        properties: {
          youtube: { $ref: '#/components/schemas/SocialProviderStatus' },
          instagram: { $ref: '#/components/schemas/SocialProviderStatus' },
          tiktok: { $ref: '#/components/schemas/SocialProviderStatus' },
        },
      },
      SocialProviderStatus: {
        type: 'object',
        properties: {
          connected: { type: 'boolean' },
          username: { type: 'string', nullable: true },
          expires_at: { type: 'string', format: 'date-time', nullable: true },
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
        tags: ['auth-compat'],
        summary: 'Registro de usuario (alias raíz)',
        description: 'Alias de compatibilidad de `POST /auth/registro` (paridad con `_compat_auth` en `main.py`).',
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
        tags: ['auth-compat'],
        summary: 'Login JSON (alias raíz)',
        description: 'Alias de compatibilidad de `POST /auth/login` (paridad con `_compat_auth` en `main.py`).',
        security: [],
        requestBody: { required: true, content: { 'application/json': { schema: { type: 'object', required: ['email', 'password'], properties: { email: { type: 'string', format: 'email' }, password: { type: 'string' } } } } } },
        responses: {
          '200': { description: 'Token', content: { 'application/json': { schema: { $ref: '#/components/schemas/Token' } } } },
          '401': { description: 'Credenciales inválidas', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
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
          { name: 'job_id', in: 'query', schema: { type: 'string', format: 'uuid' }, description: 'Filtrar por job (Issue #36)' },
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
    '/clips/{clipId}/publish-stream': {
      get: {
        tags: ['publish'],
        summary: 'SSE stream estado publicación (PUBLISHING → PUBLISHED/FAILED) — Issue #31',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'clipId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        responses: {
          '200': {
            description: 'text/event-stream',
            content: {
              'text/event-stream': {
                schema: {
                  type: 'string',
                  example: 'data: {"clip_id":"uuid","status":"PUBLISHING","publication_status":"PUBLISHING"}\n\nevent: done\ndata: {}\n\n',
                },
              },
            },
          },
        },
      },
    },
    '/clips/{clipId}/re-render': {
      post: {
        tags: ['clips'],
        summary: 'Re-renderizar clip con ASS/Hook — Issue #36',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'clipId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'object',
                properties: {
                  enable_ass: { type: 'boolean', default: true, description: 'Quemar subtítulos ASS' },
                  enable_hook: { type: 'boolean', default: true, description: 'Anteponer hook teaser' },
                },
              },
            },
          },
        },
        responses: {
          '202': { description: 'Re-render encolado PROCESSING', content: { 'application/json': { schema: { type: 'object', properties: { detail: { type: 'string' }, clip_id: { type: 'string', format: 'uuid' }, status: { type: 'string', example: 'PROCESSING' } } } } } },
          '409': { description: 'Clip ya en procesamiento' },
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
    '/videos/sample': {
      post: {
        tags: ['videos'],
        summary: 'Crear job con video de muestra (Issue 34)',
        description:
          'Copia `SAMPLE_VIDEO_PATH` (default `backend_fastapi/storage/sample/sample.mp4`) al directorio de uploads, ' +
          'crea video + job y lo ejecuta en background. Responde 202 con el JobResponse en estado PENDING.',
        security: [{ bearerAuth: [] }],
        responses: {
          '202': { description: 'Job creado', content: { 'application/json': { schema: { $ref: '#/components/schemas/JobResponse' } } } },
          '404': { description: 'Video de muestra no encontrado', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/api/videos/upload-url': {
      post: {
        tags: ['videos'],
        summary: 'Generar URL prefirmada para subir un video (R2/S3)',
        description: 'Paridad con `POST /api/videos/upload-url` de FastAPI: presigned `PUT` (900s) usando `AWS_*` y `BUCKET_NAME`.',
        security: [],
        requestBody: { required: true, content: { 'application/json': { schema: { type: 'object', required: ['file_name', 'file_type'], properties: { file_name: { type: 'string', example: 'video.mp4' }, file_type: { type: 'string', example: 'video/mp4' } } } } } },
        responses: {
          '200': { description: 'URL prefirmada y key', content: { 'application/json': { schema: { type: 'object', properties: { upload_url: { type: 'string' }, file_key: { type: 'string' } } } } } },
          '422': { description: 'Faltan file_name/file_type', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '500': { description: 'Error al generar la presigned URL', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/api/videos/process': {
      post: {
        tags: ['videos'],
        summary: 'Procesar un video almacenado en R2 mediante RunPod',
        description: 'Envía exactamente uno de `file_key` o `video_url` a RunPod Serverless. Con `file_key` se genera una presigned GET (3600s).',
        security: [],
        requestBody: { required: true, content: { 'application/json': { schema: { type: 'object', properties: { file_key: { type: 'string' }, video_url: { type: 'string' }, transcription_url: { type: 'string', nullable: true }, transcription_text: { type: 'string', nullable: true }, video_id: { type: 'string', format: 'uuid', nullable: true } } } } } },
        responses: {
          '200': { description: 'Resultado RunPod', content: { 'application/json': { schema: { type: 'object', additionalProperties: true } } } },
          '422': { description: 'Validación (exactamente uno de file_key/video_url)', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '502': { description: 'Error de RunPod', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '504': { description: 'Timeout de RunPod', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/clips/{clipId}/subtitles': {
      post: {
        tags: ['clips'],
        summary: 'Disparar subtitulado burned-in ASS para un clip',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'clipId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        responses: {
          '202': { description: 'Subtitulado encolado PROCESSING', content: { 'application/json': { schema: { type: 'object', properties: { clip_id: { type: 'string', format: 'uuid' }, status: { type: 'string', example: 'PROCESSING' }, message: { type: 'string' } } } } } },
          '403': { description: 'No autorizado', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '404': { description: 'Clip no encontrado', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '409': { description: 'Clip ya en procesamiento', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/clips/{clipId}/subtitles/status': {
      get: {
        tags: ['clips'],
        summary: 'Consultar estado de subtitulado (proxy a clip status)',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'clipId', in: 'path', required: true, schema: { type: 'string', format: 'uuid' } }],
        responses: { '200': { description: 'Clip', content: { 'application/json': { schema: { $ref: '#/components/schemas/ClipResponse' } } } } },
      },
    },
    '/auth/social/status': {
      get: {
        tags: ['social'],
        summary: 'Estado de integraciones conectadas',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'Estado por plataforma', content: { 'application/json': { schema: { $ref: '#/components/schemas/SocialStatus' } } } } },
      },
    },
    '/auth/social/accounts': {
      get: {
        tags: ['social'],
        deprecated: true,
        summary: 'Estado de integraciones conectadas (alias)',
        description: 'Alias de `GET /auth/social/status`.',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'Estado por plataforma', content: { 'application/json': { schema: { $ref: '#/components/schemas/SocialStatus' } } } } },
      },
    },
    '/auth/social/{platform}': {
      delete: {
        tags: ['social'],
        summary: 'Desconectar cuenta social',
        security: [{ bearerAuth: [] }],
        parameters: [{ name: 'platform', in: 'path', required: true, schema: { type: 'string', enum: ['youtube', 'instagram', 'tiktok'] } }],
        responses: {
          '200': { description: 'Cuenta desconectada', content: { 'application/json': { schema: { type: 'object', properties: { message: { type: 'string' } } } } } },
          '400': { description: 'Plataforma no válida', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    '/auth/social/youtube/connect': {
      get: { tags: ['social'], summary: 'Obtener URL de autorización OAuth2 de YouTube', security: [{ bearerAuth: [] }], responses: { '200': { description: 'auth_url', content: { 'application/json': { schema: { type: 'object', properties: { auth_url: { type: 'string' } } } } } }, '500': { description: 'GOOGLE_CLIENT_ID no configurado', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } } } },
    },
    '/auth/social/youtube/callback': {
      get: { tags: ['social'], summary: 'Callback OAuth2 de YouTube', security: [], parameters: [{ name: 'code', in: 'query', schema: { type: 'string' } }, { name: 'state', in: 'query', schema: { type: 'string' } }, { name: 'error', in: 'query', schema: { type: 'string' } }], responses: { '302': { description: 'Redirect al frontend con ?integration=youtube&status=success|error' } } },
    },
    '/auth/social/instagram/connect': {
      get: { tags: ['social'], summary: 'Obtener URL de autorización OAuth2 de Instagram (Meta)', security: [{ bearerAuth: [] }], responses: { '200': { description: 'auth_url', content: { 'application/json': { schema: { type: 'object', properties: { auth_url: { type: 'string' }, url: { type: 'string' } } } } } }, '500': { description: 'INSTAGRAM_CLIENT_ID / META_APP_ID no configurado', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } } } },
    },
    '/auth/social/instagram/callback': {
      get: { tags: ['social'], summary: 'Callback OAuth2 de Instagram (Meta)', security: [], parameters: [{ name: 'code', in: 'query', schema: { type: 'string' } }, { name: 'state', in: 'query', schema: { type: 'string' } }, { name: 'error', in: 'query', schema: { type: 'string' } }], responses: { '302': { description: 'Redirect al frontend con ?integration=instagram&status=success|error' } } },
    },
    '/auth/social/tiktok/connect': {
      get: { tags: ['social'], summary: 'Obtener URL de autorización OAuth2 de TikTok', security: [{ bearerAuth: [] }], responses: { '200': { description: 'auth_url', content: { 'application/json': { schema: { type: 'object', properties: { auth_url: { type: 'string' }, url: { type: 'string' } } } } } }, '500': { description: 'TIKTOK_CLIENT_KEY no configurado', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } } } },
    },
    '/auth/social/tiktok/callback': {
      get: { tags: ['social'], summary: 'Callback OAuth2 de TikTok', security: [], parameters: [{ name: 'code', in: 'query', schema: { type: 'string' } }, { name: 'state', in: 'query', schema: { type: 'string' } }, { name: 'error', in: 'query', schema: { type: 'string' } }], responses: { '302': { description: 'Redirect al frontend con ?integration=tiktok&status=success|error' } } },
    },
  },
} as const

/**
 * Paridad con FastAPI: `users.router` se incluye **sin prefijo** y con `/api`,
 * y sus rutas ya son `/users/me*` (canónicas) y `/me*` (alias). Express declara
 * el mismo par de rutas en `users.ts` y monta el router solo con esos 2 prefijos.
 */
const USERS_PREFIXES = ['', '/api'] as const

function buildUserMePaths(): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  const profileBody = {
    type: 'object',
    properties: {
      email: { type: 'string', format: 'email' },
      full_name: { type: 'string' },
      avatar_url: { type: 'string' },
      theme_preference: { type: 'string', enum: ['light', 'dark'] },
    },
  }
  const passwordBody = {
    type: 'object',
    required: ['current_password', 'new_password'],
    properties: {
      current_password: { type: 'string' },
      new_password: { type: 'string', minLength: 8, maxLength: 128 },
    },
  }
  for (const prefix of USERS_PREFIXES) {
    // Rutas canónicas `/users/me` — GET + PUT
    out[`${prefix}/users/me`] = {
      get: {
        tags: ['users'],
        summary: 'Perfil actual',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'Usuario', content: { 'application/json': { schema: { $ref: '#/components/schemas/UsuarioRead' } } } } },
      },
      put: {
        tags: ['users'],
        summary: 'Actualizar perfil',
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { 'application/json': { schema: profileBody } } },
        responses: { '200': { description: 'Actualizado' } },
      },
    }
    // Alias `/me` — GET + PUT + PATCH
    out[`${prefix}/me`] = {
      get: {
        tags: ['users'],
        summary: 'Perfil actual (alias)',
        description: 'Alias de `GET /users/me`.',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'Usuario', content: { 'application/json': { schema: { $ref: '#/components/schemas/UsuarioRead' } } } } },
      },
      put: {
        tags: ['users'],
        summary: 'Actualizar perfil (alias)',
        description: 'Alias de `PUT /users/me`.',
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { 'application/json': { schema: profileBody } } },
        responses: { '200': { description: 'Actualizado' } },
      },
      patch: {
        tags: ['users'],
        summary: 'Actualizar perfil (patch alias)',
        description: 'Alias parcial de `PUT /users/me`.',
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { 'application/json': { schema: profileBody } } },
        responses: { '200': { description: 'Actualizado' } },
      },
    }
    // Cambio de contraseña — `POST /users/me/change-password` + alias `POST /me/change-password`
    out[`${prefix}/users/me/change-password`] = {
      post: {
        tags: ['users'],
        summary: 'Cambiar contraseña',
        description: 'Verifica `current_password` y la reemplaza por `new_password` (8-128 caracteres).',
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { 'application/json': { schema: passwordBody } } },
        responses: {
          '200': { description: 'Contraseña actualizada' },
          '400': { description: 'Contraseña actual incorrecta o nueva igual a la actual', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '422': { description: 'Faltan campos o longitud inválida', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    },
    out[`${prefix}/me/change-password`] = {
      post: {
        tags: ['users'],
        summary: 'Cambiar contraseña (alias)',
        description: 'Alias de `POST /users/me/change-password`.',
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { 'application/json': { schema: passwordBody } } },
        responses: {
          '200': { description: 'Contraseña actualizada' },
          '400': { description: 'Contraseña actual incorrecta o nueva igual a la actual', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '422': { description: 'Faltan campos o longitud inválida', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    }
    // Alias PUT — solo sobre `/me/password` (FastAPI no declara `/users/me/password`)
    out[`${prefix}/me/password`] = {
      put: {
        tags: ['users'],
        summary: 'Cambiar contraseña (alias PUT)',
        description: 'Alias en `PUT` de `POST /me/change-password`.',
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { 'application/json': { schema: passwordBody } } },
        responses: {
          '200': { description: 'Contraseña actualizada' },
          '400': { description: 'Contraseña actual incorrecta o nueva igual a la actual', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
          '422': { description: 'Faltan campos o longitud inválida', content: { 'application/json': { schema: { $ref: '#/components/schemas/Error' } } } },
        },
      },
    }
  }
  return out
}

const options = {
  definition: {
    ...swaggerDefinition,
    paths: { ...swaggerDefinition.paths, ...buildUserMePaths() },
  },
  apis: ['./src/routes/*.ts', './src/controllers/*.ts'],
}

export const swaggerSpec = swaggerJSDoc(options as never)

export const swaggerUiOptions = {
  customCss: '.swagger-ui .topbar { display: none }',
  customSiteTitle: 'ClipsAI Express — Swagger UI',
  swaggerOptions: { persistAuthorization: true },
}
