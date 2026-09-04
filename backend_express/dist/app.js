import express from 'express';
import cors from 'cors';
import { statsRouter } from './routes/stats.js';
import { clipsRouter } from './routes/clips.js';
import { usersRouter } from './routes/users.js';
import { exportRouter } from './routes/export.js';
export function createApp() {
    const app = express();
    app.use(cors({
        origin: [
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'http://localhost:3001',
            'http://127.0.0.1:3001',
            'http://localhost:5173',
            'http://127.0.0.1:5173',
        ],
        credentials: true,
        methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
        allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With'],
    }));
    app.use(express.json());
    app.get('/health', (_req, res) => res.json({ status: 'ok' }));
    app.use('/', exportRouter);
    app.use('/stats', statsRouter);
    app.use('/clips', clipsRouter);
    app.use('/users', usersRouter);
    app.use('/api/users', usersRouter);
    return app;
}
