#!/usr/bin/env python3
"""
Módulo de análisis de audio para detección de eventos virales.
Usa librosa para análisis de audio sin IA.
"""

import os
import json
import librosa
import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class EventoAudio:
    """Representa un evento detectado en el audio."""
    timestamp: str
    evento: str
    intensidad: float


TIPOS_EVENTO_SCORE = {
    'grito': 4,
    'momento_intenso': 3,
    'cambio_brusco': 2,
    'cambio_escena': 1,
    'silencio': 0
}

# Zoom dinámico por RMS (issue #117): top-K picos de énfasis vocal.
PICO_ZOOM_TOP_K = 10
PICO_ZOOM_SEPARACION = 1.5


def cargar_audio(ruta: str) -> Tuple[np.ndarray, int]:
    """Carga un archivo de audio y retorna la señal y sample rate."""
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")
    
    y, sr = librosa.load(ruta, sr=None)
    duracion = len(y) / sr
    return y, sr


def calcular_rms(y: np.ndarray, sr: int, frame_length: int = 2048, hop_length: int = 512) -> Tuple[np.ndarray, np.ndarray]:
    """Calcula RMS (Root Mean Square) del audio."""
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    tiempos = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    return rms, tiempos


def _umbral_audio(rms: np.ndarray) -> Dict:
    """Umbrales de grito/silencio/cambio calculados del RMS."""
    media_rms = np.mean(rms)
    std_rms = np.std(rms)
    return {
        "grito": media_rms + 2 * std_rms,
        "silencio": media_rms * 0.3,
        "cambio": std_rms,
        "media": media_rms,
    }


def _agregar_evento_nivel(rms: np.ndarray, tiempos: np.ndarray, i: int, umbrales: Dict, eventos: list) -> None:
    """Agrega evento 'grito' o 'silencio' según el nivel del frame."""
    frame_rms = rms[i]
    tiempo = tiempos[i]

    if frame_rms > umbrales["grito"]:
        eventos.append(EventoAudio(
            timestamp=segundos_a_timestamp(tiempo),
            evento="grito",
            intensidad=float(frame_rms)
        ))

    elif frame_rms < umbrales["silencio"]:
        eventos.append(EventoAudio(
            timestamp=segundos_a_timestamp(tiempo),
            evento="silencio",
            intensidad=float(1 - frame_rms / umbrales["silencio"]) * 10
        ))


def _agregar_cambio_brusco(rms: np.ndarray, tiempos: np.ndarray, i: int, frame_rms: float, umbrales: Dict, eventos: list) -> None:
    """Agrega evento 'cambio_brusco' si hay un salto grande de energía."""
    if i > 0:
        cambio = abs(rms[i] - rms[i-1])
        if cambio > umbrales["cambio"] and frame_rms > umbrales["media"]:
            eventos.append(EventoAudio(
                timestamp=segundos_a_timestamp(tiempos[i]),
                evento="cambio_brusco",
                intensidad=float(min(cambio / umbrales["cambio"], 10))
            ))


def detectar_eventos(rms: np.ndarray, tiempos: np.ndarray) -> List[EventoAudio]:
    """Detecta eventos en el audio basándose en RMS."""
    eventos = []

    umbrales = _umbral_audio(rms)

    i = 0
    while i < len(rms):
        frame_rms = rms[i]

        _agregar_evento_nivel(rms, tiempos, i, umbrales, eventos)
        _agregar_cambio_brusco(rms, tiempos, i, frame_rms, umbrales, eventos)

        i += 1

    return eventos


def detectar_momentos_intensos(rms: np.ndarray, tiempos: np.ndarray, umbral: float = None) -> List[EventoAudio]:
    """Detecta momentos con energía alta sostenida."""
    eventos = []
    
    media_rms = np.mean(rms)
    std_rms = np.std(rms)
    
    if umbral is None:
        umbral = media_rms + 1.5 * std_rms
    
    ventana = 5
    i = 0
    while i <= len(rms) - ventana:
        chunk = rms[i:i + ventana]
        if np.mean(chunk) > umbral:
            tiempo_inicio = tiempos[i]
            eventos.append(EventoAudio(
                timestamp=segundos_a_timestamp(tiempo_inicio),
                evento="momento_intenso",
                intensidad=float(np.mean(chunk))
            ))
            i += ventana
        else:
            i += 1
    
    return eventos


def detectar_cambios_escena(y: np.ndarray, sr: int) -> List[EventoAudio]:
    """
    Detecta cambios abruptos de tema/escena usando spectral flux.
    Útil para encontrar puntos de corte naturales entre temas del video.
    """
    eventos = []
    
    try:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        
        onsets = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            units='time',
            delta=0.5,
            wait=2
        )
        
        for t in onsets:
            eventos.append(EventoAudio(
                timestamp=segundos_a_timestamp(t),
                evento="cambio_escena",
                intensidad=5.0
            ))
    except Exception as e:
        pass

    return eventos


def limpiar_eventos(eventos: List[EventoAudio], separacion_min: int = 2) -> List[EventoAudio]:
    """Elimina eventos duplicados muy cercanos."""
    if not eventos:
        return []
    
    eventos_ordenados = sorted(eventos, key=lambda x: x.timestamp)
    eventos_limpios = [eventos_ordenados[0]]
    
    for actual in eventos_ordenados[1:]:
        ultimo = eventos_limpios[-1]
        diff = timestamp_diff(ultimo.timestamp, actual.timestamp)
        
        if diff >= separacion_min:
            eventos_limpios.append(actual)
        elif actual.intensidad > ultimo.intensidad:
            eventos_limpios[-1] = actual
    
    return eventos_limpios


def timestamp_diff(ts1: str, ts2: str) -> float:
    """Calcula diferencia en segundos entre dos timestamps."""
    s1 = timestamp_a_segundos(ts1)
    s2 = timestamp_a_segundos(ts2)
    return abs(s2 - s1)


def timestamp_a_segundos(timestamp: str) -> float:
    """Convierte HH:MM:SS a segundos."""
    partes = timestamp.split(':')
    while len(partes) < 3:
        partes.insert(0, '0')
    return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])


def segundos_a_timestamp(segundos: float) -> str:
    """Convierte segundos a HH:MM:SS."""
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    return f"{horas:02d}:{minutos:02d}:{segs:02d}"


def normalizar_intensidad(eventos: List[EventoAudio]) -> List[EventoAudio]:
    """Normaliza intensidad a escala 0-10."""
    if not eventos:
        return eventos
    
    max_intensidad = max(e.intensidad for e in eventos)
    
    if max_intensidad > 0:
        for evento in eventos:
            intensidad_normalizada = (evento.intensidad / max_intensidad) * 10
            intensidad_normalizada = max(3.0, min(10.0, intensidad_normalizada))
            evento.intensidad = round(intensidad_normalizada, 1)
    
    return eventos


def filtrar_eventos(eventos: List[EventoAudio], intensidad_min: float = 3.0) -> List[EventoAudio]:
    """Elimina eventos con intensidad muy baja."""
    return [e for e in eventos if e.intensidad >= intensidad_min]


def eventos_a_dict(eventos: List[EventoAudio]) -> List[Dict]:
    """Convierte eventos a formato diccionario."""
    return [
        {
            "timestamp": e.timestamp,
            "evento": e.evento,
            "intensidad": e.intensidad
        }
        for e in eventos
    ]


def guardar_json(eventos: List[Dict], ruta: str = "audio.json") -> None:
    """Guarda los eventos en un archivo JSON."""
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(eventos, f, indent=2, ensure_ascii=False)


def _esta_separado(t: float, picos: List[float], separacion_min: float) -> bool:
    """True si t está a >= separacion_min de todos los picos ya elegidos."""
    return all(abs(t - p) >= separacion_min for p in picos)


def _picos_para_zoom(
    rms, tiempos,
    top_k: int = PICO_ZOOM_TOP_K, separacion_min: float = PICO_ZOOM_SEPARACION,
) -> List[float]:
    """Timestamps (s) de los top-K picos de énfasis vocal (issue #117).

    Ordena por intensidad de RMS y elige greedy respetando una separación
    mínima entre picos para que las ventanas de zoom no se solapen.
    """
    ordenados = sorted(zip(rms, tiempos), key=lambda par: -par[0])
    picos: List[float] = []
    for _, t in ordenados:
        if len(picos) >= top_k:
            break
        if _esta_separado(float(t), picos, separacion_min):
            picos.append(round(float(t), 3))
    return sorted(picos)


def _ruta_picos(salida_path: str) -> str:
    """Ruta del sidecar `*_picos.json` derivada del JSON de audio."""
    base, _ = os.path.splitext(str(salida_path))
    return f"{base}_picos.json"


def guardar_picos_zoom(picos: List[float], ruta: str = "audio_picos.json") -> None:
    """Guarda los picos de zoom (lista de floats) en un JSON."""
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(picos, f)


def cargar_picos(salida_path: str = "audio.json") -> List[float]:
    """Lee el sidecar de picos de zoom (`*_picos.json`); [] si no existe o falla."""
    try:
        with open(_ruta_picos(salida_path), "r", encoding="utf-8") as f:
            picos = json.load(f)
        return [float(p) for p in picos]
    except Exception:
        return []


def _features_de_eventos(eventos: List[Dict]) -> tuple:
    """Matriz de features (ts, intensidad, tipo) y su índice de evento."""
    features = []
    eventos_idx = []

    for i, evento in enumerate(eventos):
        ts = timestamp_a_segundos(evento.get('timestamp', '00:00:00'))
        intensidad = evento.get('intensidad', 5.0)
        tipo_score = TIPOS_EVENTO_SCORE.get(evento.get('evento', 'silencio'), 0)

        features.append([ts, intensidad, tipo_score])
        eventos_idx.append(i)

    return features, eventos_idx


def _indices_de_cluster(labels, cluster_id: int) -> list:
    """Índices de eventos asignados a un cluster dado."""
    return [i for i, l in enumerate(labels) if l == cluster_id]


def _mejores_por_cluster(labels, eventos: List[Dict], n_clusters_real: int) -> List[Dict]:
    """Mejor evento (por intensidad) de cada cluster."""
    mejores_por_cluster = []
    for cluster_id in range(n_clusters_real):
        indices_cluster = _indices_de_cluster(labels, cluster_id)
        if not indices_cluster:
            continue
        mejor_idx = max(indices_cluster, key=lambda i: eventos[i].get('intensidad', 0))
        mejores_por_cluster.append(eventos[mejor_idx])
    return mejores_por_cluster


def _kmeans_mejores(eventos: List[Dict], features: list, n_clusters: int) -> List[Dict]:
    """Corre KMeans y devuelve los representantes por cluster ordenados por timestamp."""
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    import numpy as np

    X = np.array(features)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    n_clusters_real = min(n_clusters, len(features))
    kmeans = KMeans(n_clusters=n_clusters_real, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    mejores_por_cluster = _mejores_por_cluster(labels, eventos, n_clusters_real)

    mejores_por_cluster.sort(key=lambda x: timestamp_a_segundos(x.get('timestamp', '00:00:00')))

    return mejores_por_cluster


def _orden_por_intensidad(eventos: List[Dict]) -> List[Dict]:
    """Fallback: eventos ordenados por intensidad descendente."""
    return sorted(eventos, key=lambda x: x.get('intensidad', 0), reverse=True)


def detectar_momentos_virales_clustering(
    eventos: List[Dict], 
    n_clusters: int = 10
) -> List[Dict]:
    """
    Usa KMeans clustering para identificar los momentos más representativos
    y diversos del video, evitando clusters de momentos similares repetidos.
    """
    try:
        features, eventos_idx = _features_de_eventos(eventos)

        if len(features) < n_clusters:
            return _orden_por_intensidad(eventos)

        return _kmeans_mejores(eventos, features, n_clusters)

    except Exception as e:
        return _orden_por_intensidad(eventos)


def _guardar_momentos_virales(eventos_dict: List[Dict]) -> None:
    """Guarda el clustering de momentos virales (best-effort, issue #117)."""
    try:
        momentos_virales = detectar_momentos_virales_clustering(eventos_dict, n_clusters=10)
        guardar_json(momentos_virales, "momentos_virales.json")
    except Exception:
        pass


def analizar_audio(audio_path: str = "audio.mp3", salida_path: str = "audio.json") -> List[Dict]:
    """
    Función principal: analiza un archivo de audio y genera audio.json.
    
    Args:
        audio_path: Ruta al archivo de audio (MP3)
        salida_path: Ruta donde guardar el JSON de salida
    
    Returns:
        Lista de diccionarios con los eventos detectados
    """
    
    try:
        y, sr = cargar_audio(audio_path)
        rms, tiempos = calcular_rms(y, sr)
        
        eventos = detectar_eventos(rms, tiempos)
        
        momentos_intensos = detectar_momentos_intensos(rms, tiempos)
        
        cambios_escena = detectar_cambios_escena(y, sr)
        
        eventos.extend(momentos_intensos)
        eventos.extend(cambios_escena)
        
        eventos = limpiar_eventos(eventos, separacion_min=2)
        
        eventos = normalizar_intensidad(eventos)
        
        eventos = filtrar_eventos(eventos, intensidad_min=3.0)

        # Sidecar de picos RMS para zoompan (issue #117): se escribe SIEMPRE,
        # incluso sin eventos, para que el render tenga zoom si hay énfasis vocal.
        guardar_picos_zoom(_picos_para_zoom(rms, tiempos), _ruta_picos(salida_path))

        if not eventos:
            return []

        eventos_dict = eventos_a_dict(eventos)
        guardar_json(eventos_dict, salida_path)
        _guardar_momentos_virales(eventos_dict)

        return eventos_dict
        
    except FileNotFoundError as e:
        return []
    except Exception as e:
        return []


def main():
    """Ejemplo de uso."""
    import sys
    
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "audio.mp3"
    salida_path = sys.argv[2] if len(sys.argv) > 2 else "audio.json"
    
    analizar_audio(audio_path, salida_path)


if __name__ == "__main__":
    main()
