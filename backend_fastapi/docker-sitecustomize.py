"""Sitecustomize: reordena PATH para que los binarios del sistema (ffmpeg con libx264)
tengan prioridad sobre los de /opt/conda.

Python lo importa automáticamente al arrancar el intérprete si está en
/usr/local/lib/pythonX.Y/site-packages/.

Requisitos:
  - Idempotente (seguro de correr N veces).
  - No falla si PATH no existe.
  - No imprime nada en stdout.
"""

import os as _os

_DESIRED_PREFIX = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

try:
    _current = _os.environ.get("PATH", "")
    if _current:
        _parts = [p for p in _current.split(":") if p]
        _seen = set()
        _ordered = []
        for p in _parts:
            if p not in _seen:
                _seen.add(p)
                _ordered.append(p)
        _desired_parts = [p for p in _DESIRED_PREFIX.split(":") if p]
        _final = []
        for p in _desired_parts:
            if p not in _final:
                _final.append(p)
        for p in _ordered:
            if p not in _final:
                _final.append(p)
        _os.environ["PATH"] = ":".join(_final)
except Exception:
    pass
