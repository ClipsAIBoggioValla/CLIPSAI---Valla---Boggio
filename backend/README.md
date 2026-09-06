# Backend Decoupled — Guía de Tracks

**Objetivo:** dos devs en paralelo sin bloqueos.

```
backend/
  core/           ← CONTRATOS (única zona compartida, no lógica)
    schemas.py    ← Pydantic WordToken, TranscriptData, ViralClipCandidate, RenderConfig, ScheduledPost
    interfaces.py ← ABCs ITranscriber, IAudioAnalyzer, IIngestionService, IViralityEngine, IRenderer, IPublisher
  track_a/        ← Compañero owner
    ingestion/service.py  (video → video_id)
    audio/analyzer.py     (video_id → AudioFeatures)
    transcription/stt.py  (video_id → TranscriptData)
  track_b/        ← Yo owner
    virality/engine.py    (TranscriptData+AudioFeatures → ViralClipCandidate[])
    rendering/ffmpeg.py   (clip + RenderConfig → 1080x1920 mp4)
    rendering/captions.py (WordToken[] → .ass karaoke)
    publishing/scheduler.py (ScheduledPost → url)
  shared/         ← config, utils sin lógica de dominio
```

## Reglas de Paralelo
1. **Solo `backend/core` es compartido.** Cambios ahí requieren PR + review de ambos.
2. **Track A nunca importa `track_b` y viceversa.** Solo `core`.
3. **Stubs ya compilan:** cada servicio tiene implementación mock que respeta la interfaz. Tests pueden correr sin FFmpeg ni API keys.
4. **Handoff tipado:** `TranscriptData` y `AudioFeatures` son el contrato A→B. `ViralClipCandidate` + `RenderConfig` es B interno. `ScheduledPost` es salida a redes.
5. **SSE/Job:** `AutopilotJob` con `status: pending|transcribing|analyzing_audio|scoring|rendering|ready|publishing|completed|failed` + `progress 0-100` es el estado que consume la UI Autopilot.

## Cómo trabajar

```bash
# Track A dev
python -m backend.track_a.transcription.stt
python -m backend.track_a.audio.analyzer

# Track B dev
python -m backend.track_b.virality.engine
python -m backend.track_b.rendering.ffmpeg
```

Ambos importan solo:
```python
from backend.core.schemas import TranscriptData, ViralClipCandidate, RenderConfig
from backend.core.interfaces import ITranscriber, IViralityEngine
```

## Próximos pasos
- Wirear `backend_fastapi` y `backend_express` para que importen `backend.core.schemas` en vez de sus schemas duplicados.
- `docker-compose` monta `backend` como volumen para ambos backends.
