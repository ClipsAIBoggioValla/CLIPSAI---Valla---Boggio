const { spawn } = require('child_process');
const path = require('path');

/**
 * Invoca el engine_subprocess.py de Python desde Node.js
 */
function runEngineSubprocess(videoPath, transcriptionPath) {
  return new Promise((resolve, reject) => {
    const pythonScript = path.resolve(__dirname, '../../../engine_subprocess.py');
    const pythonProcess = spawn('python', [pythonScript, '--video', videoPath, '--transcription', transcriptionPath]);

    let stdoutData = '';
    let stderrData = '';

    pythonProcess.stdout.on('data', (data) => {
      stdoutData += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      stderrData += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (code !== 0) {
        return reject(new Error(`Engine process failed with code ${code}: ${stderrData}`));
      }
      try {
        const result = JSON.parse(stdoutData);
        resolve(result);
      } catch (parseErr) {
        reject(new Error(`Failed to parse engine JSON output: ${stdoutData}`));
      }
    });
  });
}

module.exports = { runEngineSubprocess };