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
          transcript: { type: 'string', nullable: true },
          status: { type: 'string', nullable: true, example: 'ready' },
          file_path: { type: 'string', nullable: true, example: '/app/storage/clips/abc.mp4' },
          stream_url: { type: 'string', example: '/clips/abc/descarga' },
          duration: { type: 'number', nullable: true, example: 17.5 },
          has_ass: { type: 'boolean', example: true },
          has_hook: { type: 'boolean', example: true },
          tags: { type: 'object', nullable: true },
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
          publication_status: { type: 'string', nullable: true },
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
    '/metrics': {
      get: {
        tags: ['metrics'],
        summary: 'Métricas 7 días',
        security: [{ bearerAuth: [] }],
        responses: { '200': { description: 'Metrics', content: { 'application/json': { schema: { $ref: '#/components/schemas/MetricsResponse' } } } } },
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
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { 'application/json': { schema: { type: 'object', required: ['current_password', 'new_password'], properties: { current_password: { type: 'string' }, new_password: { type: 'string', minLength: 8, maxLength: 128 } } } } } },
        responses: { '200': { description: 'OK' } },
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
