"""Utilidades compartidas para parsing de transcripción de texto a segmentos.

Contiene la lógica de parseo de líneas con timestamps (formato HH:MM:SS - texto
o MM:SS - texto o [start - end] texto) y líneas sin timestamp (ventana sintética
de 3 segundos). Ambas implementaciones (jobs.py y engine.py) ahora comparten esta
función para evitar duplicación (Issue 42 — Duplic%).
"""
from __future__ import annotations

import re
from typing import List, Dict

from sqlalchemy.orm import Session as SessionType


def parse_transcript_text_to_segments(text: str) -> List[Dict[str, float]]:
    """Convierte texto plano o líneas con timestamps a una lista de segmentos.

    Formatos admitidos por línea:
      - "HH:MM:SS - texto" o "MM:SS - texto"
      - "[start - end] texto"
      - línea sin timestamp → ventana sintética de 3s desde el cursor

    Returns
    -------
    list[dict]
        Cada dict tiene claves ``start``, ``end``, ``text``.
    """
    segs: List[Dict[str, float]] = []
    if not text or not text.strip():
        return segs
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    re_ts = re.compile(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*(.+)$")
    re_bracket = re.compile(r"^\[\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*\]\s*(.+)$")
    cursor = 0.0
    for line in lines:
        m = re_bracket.match(line)
        if m:
            try:
                s = float(m.group(1))
                e = float(m.group(2))
                t = m.group(3).strip()
                if e > s and t:
                    segs.append({"start": s, "end": e, "text": t})
                continue
            except Exception:
                pass
        m = re_ts.match(line)
        if m:
            ts_str = m.group(1)
            t = m.group(2).strip()
            # Convierte ts a segundos
            try:
                parts = ts_str.split(":")
                if len(parts) == 3:
                    s = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                elif len(parts) == 2:
                    s = int(parts[0]) * 60 + float(parts[1])
                else:
                    s = float(parts[0])
                e = s + 3.0
                if t:
                    segs.append({"start": s, "end": e, "text": t})
                continue
            except Exception:
                pass
        # Línea sin timestamp: asigna ventana sintética 3s
        segs.append({"start": cursor, "end": cursor + 3.0, "text": line})
        cursor += 3.0
    return segs