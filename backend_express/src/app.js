require('dotenv').config();
const express = require('express');
const cors = require('cors');

const authRouter = require('./routes/auth');
const videosRouter = require('./routes/videos');
const jobsRouter = require('./routes/jobs');
const clipsRouter = require('./routes/clips');
const { migrate } = require('./config/database');

const app = express();
const PORT = process.env.PORT || 8001;

// Middlewares globales
app.use(cors());
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true }));

// Health check (misma forma que FastAPI)
app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

// Enrutadores principales (Mismas rutas base que FastAPI)
app.use('/auth', authRouter);
app.use('/videos', videosRouter);
// Jobs router maneja /jobs y /videos/:video_id/jobs
app.use('/', jobsRouter);
app.use('/clips', clipsRouter);

// Manejador 404
app.use((req, res) => {
  res.status(404).json({ detail: 'Not Found' });
});

// Manejador de errores: JSON invalido -> 400, resto -> 500
app.use((err, req, res, next) => {
  if (err.type === 'entity.parse.failed' || err.status === 400) {
    return res.status(400).json({ detail: 'There was an error parsing the body' });
  }

  console.error(err.stack);
  res.status(500).json({ detail: 'Internal Server Error' });
});

// Inicialización del servidor
if (require.main === module) {
  migrate()
    .then(() => {
      app.listen(PORT, () => {
        console.log(`🚀 Servidor Express activo en http://localhost:${PORT}`);
      });
    })
    .catch((err) => {
      console.error('Fallo la migracion de la base de datos:', err);
      process.exit(1);
    });
}

module.exports = app;
