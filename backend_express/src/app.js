require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');

const authRouter = require('./routes/auth');
const videosRouter = require('./routes/videos');
const jobsRouter = require('./routes/jobs');
const clipsRouter = require('./routes/clips');

const app = express();
const PORT = process.env.PORT || 8001;

// Middlewares globales
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Archivos estáticos
app.use('/uploads', express.static(path.resolve(__dirname, '../uploads')));

// Enrutadores principales (Mismas rutas base que FastAPI)
app.use('/auth', authRouter);
app.use('/videos', videosRouter);
app.use('/jobs', jobsRouter);
app.use('/clips', clipsRouter);

// Manejador 404
app.use((req, res) => {
  res.status(404).json({ detail: 'Not Found' });
});

// Manejador de errores general 500
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ detail: 'Internal Server Error', error: err.message });
});

// Inicialización del servidor
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`🚀 Servidor Express activo en http://localhost:${PORT}`);
  });
}

module.exports = app;