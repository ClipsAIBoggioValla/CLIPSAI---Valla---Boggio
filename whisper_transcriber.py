#!/usr/bin/env python3
"""
Transcripción de video para detección de clips virales.
Genera transcripcion_formatted.txt para que la IA analice el contenido.

Modos:
  A) Con transcripcion.txt manual → parser determinístico (instantáneo)
  B) Sin transcripción → faster-whisper large-v3-turbo (5-6 min)
"""

import os
import re
import subprocess
import time
from typing import List


def segundos_a_ms(seg: float) -> str:
    m = int(seg // 60)
    s = int(seg % 60)
    return f"{m}:{s:02d}"


def segundos_a_hhmmss(seg: float) -> str:
    h = int(seg // 3600)
    m = int((seg % 3600) // 60)
    s = int(seg % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def detectar_device() -> tuple:
    try:
        import torch
        if torch.cuda.is_available():
            return ("cuda", "float16")
    except Exception:
        pass
    return ("cpu", "int8")


def _extraer_audio(video_path: str) -> str:
    audio_temp = "audio_trans_temp.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        audio_temp
    ], capture_output=True, check=True)
    return audio_temp


def _remover_descripcion(texto: str) -> str:
    """
    Remueve descripción de tiempo al inicio del texto.
    Maneja texto pegado sin espacio.
    """
    patrones_desc = [
        re.compile(r'^\d+\s+minutos?\s+y\s+\d+\s+segundos?', re.IGNORECASE),
        re.compile(r'^\d+\s+minutos?(?!\s+y)', re.IGNORECASE),
        re.compile(r'^\d+\s+segundos?', re.IGNORECASE),
    ]
    for patron in patrones_desc:
        m = patron.match(texto)
        if m:
            resto = texto[len(m.group(0)):]
            return resto.lstrip()
    return texto


def parsear_transcripcion_youtube(
    ruta: str,
    salida: str = "transcripcion_formatted.txt"
) -> str:
    """Parsea transcripción cruda de YouTube al formato HH:MM:SS - Texto."""
    
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read().strip()
    
    lineas = contenido.split('\n')
    segmentos = []
    timestamp_actual = None
    texto_pendiente = ""
    
    RE_TS = re.compile(r'^(\d{1,2}:\d{2}(?::\d{2})?)')
    RE_LIMPIO = re.compile(r'^\d{2}:\d{2}:\d{2}\s*-\s*')
    
    def _ts_a_hhmmss(ts: str) -> str:
        partes = ts.split(':')
        if len(partes) == 2:
            return f"00:{int(partes[0]):02d}:{int(partes[1]):02d}"
        elif len(partes) == 3:
            return f"{int(partes[0]):02d}:{int(partes[1]):02d}:{int(partes[2]):02d}"
        return "00:00:00"
    
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        
        if RE_LIMPIO.match(linea):
            if texto_pendiente and timestamp_actual:
                segmentos.append((timestamp_actual, texto_pendiente.strip()))
            timestamp_actual = linea[:8]
            texto_pendiente = RE_LIMPIO.sub('', linea).strip()
            continue
        
        match = RE_TS.match(linea)
        if match:
            if texto_pendiente and timestamp_actual:
                segmentos.append((timestamp_actual, texto_pendiente.strip()))
            
            ts_raw = match.group(1)
            timestamp_actual = _ts_a_hhmmss(ts_raw)
            resto = linea[len(ts_raw):]
            resto = _remover_descripcion(resto.strip())
            texto_pendiente = resto
        else:
            if texto_pendiente:
                texto_pendiente += " " + linea
    
    if texto_pendiente and timestamp_actual:
        segmentos.append((timestamp_actual, texto_pendiente.strip()))
    
    with open(salida, 'w', encoding='utf-8') as f:
        for ts, texto in segmentos:
            if texto:
                f.write(f"{ts} - {texto}\n")
    
    return salida
