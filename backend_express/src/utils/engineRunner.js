const { spawn } = require('child_process');
const path = require('path');

const PYTHON = process.env.CLIPSAI_PYTHON || 'python3';

/**
 * Invoca el motor de clips de Python desde Node.js y parsea su salida JSON.
 * Por defecto usa scripts/run_clip_engine.py, que replica la logica del
 * servicio de motor de FastAPI (misma carga util simulada/real).
 */
function runEngineSubprocess(videoPath, transcriptionPath) {
  return new Promise((resolve, reject) => {
    const pythonScript = path.resolve(__dirname, '../../scripts/run_clip_engine.py');

    const pythonProcess = spawn(PYTHON, [pythonScript, videoPath, transcriptionPath]);

    let stdoutData = '';
    let stderrData = '';

    pythonProcess.stdout.on('data', (data) => {
      stdoutData += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      stderrData += data.toString();
    });

    pythonProcess.on('close', (code) => {
      let result = null;
      try {
        result = JSON.parse(stdoutData);
      } catch (parseErr) {
        result = null;
      }

      if (result && result.exito === false) {
        return reject(new Error(result.error || result.error_detalle || 'Engine error'));
      }

      if (result && result.error) {
        return reject(new Error(result.error));
      }

      if (code !== 0) {
        return reject(new Error(`Engine process failed with code ${code}: ${stderrData}`));
      }

      if (result) {
        return resolve(result);
      }

      reject(new Error(`Failed to parse engine JSON output: ${stdoutData}`));
    });
  });
}

module.exports = { runEngineSubprocess };
