"""Compatibilidad histórica del contrato de re-trim (Issue #121).

La implementación vive en ``backend_fastapi.app.routers.retrim`` para compartir
el mismo código en el layout plano (``app.*``) y en el layout del repositorio
(``backend_fastapi.app.*``). Este módulo conserva la ruta pública que ya
documentaban los tests y el paquete ``backend``.
"""

from backend_fastapi.app.routers.retrim import (  # noqa: F401
    RetrimOptionsResponse,
    RetrimRequest,
    RetrimResponse,
    SubtitleCue,
    router,
)

__all__ = [
    "RetrimOptionsResponse",
    "RetrimRequest",
    "RetrimResponse",
    "SubtitleCue",
    "router",
]
