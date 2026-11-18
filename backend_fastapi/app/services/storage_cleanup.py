"""Limpieza de archivos locales en el disco persistente de Render.

Evita que /var/data se llene con uploads y clips acumulados.
Se usa desde 3 puntos:
  - startup de FastAPI (limpieza inicial)
  - finally de cada job (limpieza post-job)
  - antes de guardar un upload nuevo (ensure_disk_space)
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _resolve_base_path(base_path: Optional[str]) -> Path:
    if base_path:
        return Path(base_path)
    candidate = (
        os.environ.get("STORAGE_DIR")
        or os.environ.get("STORAGE_PATH")
        or "/var/data"
    )
    return Path(candidate)


def _archivos_de_subcarpeta(child: Path) -> list[Path]:
    """Archivos recursivos de una subcarpeta típica (ignora fallos)."""
    targets: list[Path] = []
    for f in child.rglob("*"):
        try:
            if f.is_file():
                targets.append(f)
        except Exception:
            continue
    return targets


def _es_subcarpeta_tipica(child: Path, subfolders: set[str]) -> bool:
    """True si es directorio de una de las subcarpetas típicas."""
    return child.is_dir() and child.name in subfolders


def _es_archivo_borrable(child: Path) -> bool:
    """True si es un archivo suelto con extensión de video/audio/subtítulos."""
    return child.is_file() and child.suffix.lower() in {".mp4", ".ass", ".mp3"}


def _destino_de_child(child: Path, subfolders: set[str]) -> list[Path]:
    """Archivos a borrar aportados por un hijo del base."""
    try:
        if _es_subcarpeta_tipica(child, subfolders):
            return _archivos_de_subcarpeta(child)
        if _es_archivo_borrable(child):
            return [child]
    except Exception:
        pass
    return []


def _collect_targets(base: Path) -> list[Path]:
    """Recopila archivos candidatos a borrar en base y sus subcarpetas típicas."""
    targets: list[Path] = []
    subfolders = {"uploads", "clips", "temp", "tmp"}
    try:
        if not base.exists():
            return targets
        for child in base.iterdir():
            targets.extend(_destino_de_child(child, subfolders))
    except Exception:
        pass
    return targets


def _infos_con_edad(targets: list[Path]) -> list[tuple]:
    """(path, mtime, size) de cada target; omite los que fallen."""
    info_with_age = []
    for p in targets:
        try:
            st = p.stat()
            info_with_age.append((p, st.st_mtime, st.st_size))
        except Exception:
            continue
    return info_with_age


def _borrar_viejos(info_with_age: list[tuple], cutoff: float) -> int:
    """Borra los archivos con mtime anterior al corte. Devuelve bytes liberados."""
    freed = 0
    for p, mtime, size in info_with_age:
        try:
            if mtime < cutoff:
                p.unlink()
                freed += size
        except Exception:
            continue
    return freed


def _restantes_con_edad(targets: list[Path]) -> list[tuple]:
    """(path, mtime, size) de los targets que siguen existiendo, más viejo primero."""
    remaining = []
    for p in targets:
        try:
            if p.exists():
                st = p.stat()
                remaining.append((p, st.st_mtime, st.st_size))
        except Exception:
            continue
    remaining.sort(key=lambda t: t[1])  # más viejo primero
    return remaining


def _total_bytes(remaining: list[tuple]) -> int:
    """Suma de tamaños de las tuplas (path, mtime, size)."""
    return sum(s for _, _, s in remaining)


def _podar_por_total(remaining: list[tuple], max_total_bytes: int, freed: int) -> int:
    """Borra los más viejos hasta bajar del límite total. Devuelve bytes acumulados."""
    current_total = _total_bytes(remaining)
    for p, _mtime, size in remaining:
        if current_total <= max_total_bytes:
            break
        try:
            p.unlink()
            freed += size
            current_total -= size
        except Exception:
            continue
    return freed


def cleanup_storage(
    base_path: Optional[str] = None,
    max_age_hours: int = 24,
    max_total_mb: int = 500,
) -> int:
    """Limpia archivos locales viejos o excesivos.

    Reglas:
      a) base_path por defecto = STORAGE_DIR o STORAGE_PATH env, o "/var/data".
      b) Recorre subcarpetas (uploads, clips, temp, tmp) y archivos .mp4/.ass/.mp3
         sueltos; borra los con mtime > max_age_hours.
      c) Si el total restante supera max_total_mb, borra los más viejos primero
         hasta bajar del límite.
      d) Loguea "[storage] cleanup liberó X MB".
      e) NUNCA propaga excepciones al caller.

    Returns:
        Bytes liberados (int >= 0).
    """
    freed_bytes = 0
    try:
        base = _resolve_base_path(base_path)
        targets = _collect_targets(base)

        cutoff = time.time() - (max_age_hours * 3600)
        info_with_age = _infos_con_edad(targets)

        # Fase 1: borrar todo lo más viejo que max_age_hours
        freed_bytes = _borrar_viejos(info_with_age, cutoff)

        # Fase 2: si aún supera max_total_mb, borrar los más viejos primero
        remaining = _restantes_con_edad(targets)
        max_total_bytes = max_total_mb * 1024 * 1024
        freed_bytes = _podar_por_total(remaining, max_total_bytes, freed_bytes)

        freed_mb = freed_bytes / (1024 * 1024)
        logger.info("[storage] cleanup liberó %.2f MB en %s (max_age=%dh, max_total=%dMB)",
                    freed_mb, base, max_age_hours, max_total_mb)
    except Exception as exc:
        logger.error("[storage] cleanup_storage falló (no propagado): %s", exc)
    return freed_bytes


def ensure_disk_space(path: str | Path, min_free_mb: int = 500) -> int:
    """Garantiza al menos min_free_mb libres en el filesystem que contiene `path`.

    Si free < min_free_mb:
      - ejecuta cleanup_storage forzado (ignorando max_age, borrando más viejos primero)
      - re-chequea y, si sigue insuficiente, repite hasta liberar o quedarse sin candidatos.

    Returns:
        Bytes libres actuales (int >= 0).
    """
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(str(target))
        free_mb = usage.free / (1024 * 1024)
        if free_mb >= min_free_mb:
            return usage.free

        logger.warning(
            "[storage] espacio insuficiente (%.1f MB libres, mínimo %d MB); forzando cleanup",
            free_mb, min_free_mb,
        )

        base = _resolve_base_path(None)
        freed = cleanup_storage(base_path=str(base), max_age_hours=0, max_total_mb=min_free_mb)
        logger.info("[storage] ensure_disk_space liberó %.2f MB forzadamente", freed / (1024 * 1024))

        usage = shutil.disk_usage(str(target))
        free_mb_after = usage.free / (1024 * 1024)
        logger.info("[storage] espacio tras ensure_disk_space: %.1f MB libres", free_mb_after)
        return usage.free
    except Exception as exc:
        logger.error("[storage] ensure_disk_space falló (no propagado): %s", exc)
        return 0
