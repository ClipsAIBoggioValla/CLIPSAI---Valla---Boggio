import express from 'express';
import cors from 'cors';
import swaggerUi from 'swagger-ui-express';
import { swaggerSpec, swaggerUiOptions } from './docs/swagger.js';
import { statsRouter } from './routes/stats.js';
import { clipsRouter } from './routes/clips.js';
import { usersRouter } from './routes/users.js';
import { exportRouter } from './routes/export.js';
import { metricsRouter } from './routes/metrics.js';
import { authRouter } from './routes/auth.js';
import { videosRouter } from './routes/videos.js';
import { jobsRouter } from './routes/jobs.js';
import { publishRouter } from './routes/publish.js';
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
    // Swagger UI — Issue #30 paridad FastAPI /docs
    app.use('/docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec, swaggerUiOptions));
    app.get('/openapi.json', (_req, res) => res.json(swaggerSpec));
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
    app.use(authRouter);
    app.use('/videos', videosRouter);
    app.use('/', jobsRouter);
    app.use('/', exportRouter);
    app.use('/', metricsRouter);
    app.use('/stats', statsRouter);
    app.use('/clips', clipsRouter);
    app.use('/', publishRouter);
    app.use('/users', usersRouter);
    app.use('/api/users', usersRouter);
    return app;
}
