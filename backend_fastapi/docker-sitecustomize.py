"""Alias de paquete para la imagen Docker de FastAPI.

Contexto
--------
`backend_fastapi/app/main.py` importa condicionalmente `backend.api.routes.retrim`
y `backend.api.routes.stream`. Esos dos módulos hacen
`from backend_fastapi.app.database import ...`, que solo resuelve cuando el repo
está en `sys.path` con su layout de raíz (`main.py` busca un ancestro que contenga
`backend/` o `backend_fastapi/`).

Dentro de la imagen la app vive en `/app` y se importa como `app.*`. Ahí `main.py`
sí resuelve `_root = /app`, pero el nombre `backend_fastapi.app.*` no existe, así
que el import fallaba y quedaba `retrim_router = stream_router = None`: las rutas
`GET /jobs/{job_id}/stream` y `POST /clips/{clip_id}/retrim` no se montaban y la
superficie de la API dependía del layout de ejecución (60 rutas en Docker vs 62
desde la raíz del repo).

Qué hace este archivo
---------------------
Se instala como `sitecustomize.py` (Python lo importa automáticamente al arrancar,
antes de cualquier código de la app) e instala un meta-path finder que reenvía
`backend_fastapi.*` a `app.*` **reutilizando los mismos objetos módulo**. Así no se
duplica el `MetaData`/registry de SQLAlchemy ni se crea un segundo engine: sigue
habiendo una única fuente de verdad. Actúa **solo como fallback**: si el módulo real
`backend_fastapi.*` es importable (p. ej. al correr desde la raíz del repo, donde
los tests y cualquier consumidor legítimo lo usan), se devuelve `None` y el import
normal sigue su curso. Así no se interfiere con el layout de repo; solo se arregla
la imagen Docker, donde ese paquete no existe.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from importlib.machinery import PathFinder

_PKG = "backend_fastapi"


def _target_name(fullname: str) -> str | None:
    """Devuelve el módulo real que corresponde a un nombre alias.

    `backend_fastapi` y `backend_fastapi.app` son el mismo paquete `app`; los
    submódulos se reenvían tal cual (`backend_fastapi.app.database` -> `app.database`).
    """
    if fullname == _PKG or fullname == f"{_PKG}.app":
        return "app"
    if fullname.startswith(f"{_PKG}.app."):
        return "app." + fullname[len(f"{_PKG}.app.") :]
    return None


class _AliasLoader:
    """Loader que reutiliza el módulo real importado bajo su nombre destino."""

    def create_module(self, spec):
        target = _target_name(spec.name)
        if target is None:
            return None
        # Importa el módulo real (p. ej. `app.database`) y lo reutiliza tal cual.
        return importlib.import_module(target)

    def exec_module(self, module):  # noqa: D102
        # El módulo ya quedó inicializado por `create_module`.
        return None


class _PackageAliasFinder:
    """Meta-path finder que reenvía `backend_fastapi.*` a `app.*`.

    Actúa **solo como fallback**: si el módulo real `backend_fastapi.*` es
    importable (p. ej. al correr desde la raíz del repo, donde los tests y
    cualquier consumidor legítimo lo usan), se devuelve `None` y el import normal
    sigue su curso. Así no se interfiere con el layout de repo; solo se arregla la
    imagen Docker, donde ese paquete no existe.
    """

    def find_spec(self, fullname, path=None, target=None):  # noqa: D102
        if _target_name(fullname) is None:
            return None
        if PathFinder.find_spec(fullname, path) is not None:
            return None
        return importlib.util.spec_from_loader(fullname, loader=_AliasLoader())


if not any(isinstance(finder, _PackageAliasFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _PackageAliasFinder())
