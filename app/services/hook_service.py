"""Re-exporta el hook_service canónico (backend_fastapi.app.services) — issue #115.

La copia en la raíz estaba divergente (48+/15-) y ningún módulo la importa
(el worker RunPod usa `backend/` + `engine.py`, no `app/services`). Única
fuente de verdad: `backend_fastapi/app/services/hook_service.py` — este
archivo solo re-exporta la API pública para compatibilidad con imports
legacy (`from app.services.hook_service import detect_hooks`).
"""

from __future__ import annotations

from backend_fastapi.app.services.hook_service import (  # noqa: F401
    HookClip,
    detect_hooks,
    detect_hooks_from_transcript_file,
)

__all__ = ["HookClip", "detect_hooks", "detect_hooks_from_transcript_file"]
