import express from 'express';
import cors from 'cors';
import swaggerUi from 'swagger-ui-express';
import { swaggerSpec, swaggerUiOptions } from './docs/swagger.js';
import { statsRouter } from './routes/stats.js';
import { clipsRouter } from './routes/clips.js';
import { subtitlesRouter } from './routes/subtitles.js';
import { usersRouter } from './routes/users.js';
import { exportRouter } from './routes/export.js';
import { metricsRouter } from './routes/metrics.js';
import { authRouter, compatAuthRouter } from './routes/auth.js';
import { videosRouter } from './routes/videos.js';
import { apiVideosRouter } from './routes/apiVideos.js';
import { jobsRouter } from './routes/jobs.js';
import { publishRouter } from './routes/publish.js';
import { socialAuthRouter } from './routes/socialAuth.js';
export function createApp() {
    const app = express();
    app.use(cors({
        origin: [
            'https://decorator-excretory-satin.ngrok-free.dev',
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'http://localhost:5173',
            'http://127.0.0.1:5173',
            'http://localhost:3001',
            'http://127.0.0.1:3001',
        ],
        credentials: true,
        methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
        allowedHeaders: ['Authorization', 'Content-Type', 'ngrok-skip-browser-warning', 'X-Requested-With', 'Accept', 'Origin'],
        exposedHeaders: ['*'],
        optionsSuccessStatus: 200,
    }));
    app.options('/*', cors({
        origin: [
            'https://decorator-excretory-satin.ngrok-free.dev',
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'http://localhost:5173',
            'http://127.0.0.1:5173',
            'http://localhost:3001',
            'http://127.0.0.1:3001',
        ],
        credentials: true,
        allowedHeaders: ['Authorization', 'Content-Type', 'ngrok-skip-browser-warning', 'X-Requested-With', 'Accept', 'Origin'],
        optionsSuccessStatus: 200,
    }));
    app.use(express.json());
    app.use(express.urlencoded({ extended: true }));
    // Swagger UI — Issue 14/30 paridad FastAPI /docs
    // `/api-docs` es el criterio de aceptación de Issue 14; `/docs` se mantiene por compatibilidad.
    const swaggerUiHandler = swaggerUi.setup(swaggerSpec, swaggerUiOptions);
    app.use('/docs', swaggerUi.serve, swaggerUiHandler);
    app.use('/api-docs', swaggerUi.serve, swaggerUiHandler);
    app.get('/openapi.json', (_req, res) => res.json(swaggerSpec));
    app.get('/api-docs.json', (_req, res) => res.json(swaggerSpec));
    // Paridad FastAPI: `/redoc` y `/docs/oauth2-redirect` ( viewers alternativos del mismo spec).
    app.get('/redoc', (_req, res) => {
        res.type('html').send('<!DOCTYPE html><html><head><title>ClipsAI Express API — ReDoc</title>' +
            '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
            '<style>body{margin:0}</style></head><body>' +
            '<redoc spec-url="/openapi.json"></redoc>' +
            '<script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>' +
            '</body></html>');
    });
    app.get('/docs/oauth2-redirect', (_req, res) => {
        res.type('html').send('<!DOCTYPE html><html><head><title>OAuth2 Redirect</title>' +
            '<script>window.onload=function(){if(window.opener&&window.opener.swaggerUIRedirectOauth2){' +
            'window.opener.swaggerUIRedirectOauth2(window.location.hash)}}</script></head><body></body></html>');
    });
    /**
     * @openapi
     * /health:
     *   get:
     *     tags: [infra]
     *     summary: Healthcheck simple
     *     description: Verifica que el servicio Express esté operativo. Usado por docker healthcheck y por el frontend para validar paridad con FastAPI.
     *     responses:
     *       200:
     *         description: Servicio operativo
     *         content:
     *           application/json:
     *             schema:
     *               type: object
     *               properties:
     *                 status:
     *                   type: string
     *                   example: ok
     */
    app.get('/health', (_req, res) => res.json({ status: 'ok' }));
    app.use('/auth', authRouter);
    app.use('/auth/social', socialAuthRouter);
    app.use(compatAuthRouter);
    app.use('/videos', videosRouter);
    app.use('/api/videos', apiVideosRouter);
    app.use('/', jobsRouter);
    app.use('/', exportRouter);
    app.use('/', metricsRouter);
    app.use('/stats', statsRouter);
    app.use('/clips', clipsRouter);
    app.use('/clips', subtitlesRouter);
    app.use('/', publishRouter);
    // Paridad con FastAPI: `users.router` se incluye sin prefijo y con `/api`
    // (sus rutas ya son `/users/me*` y `/me*`), exponiendo `/users/me`, `/me`,
    // `/api/users/me` y `/api/me`.
    app.use(usersRouter);
    app.use('/api', usersRouter);
    return app;
}
