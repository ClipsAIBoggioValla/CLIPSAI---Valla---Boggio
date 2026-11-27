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
import threading
import time
from pathlib import Path
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


RE_TS_YT = re.compile(r'^(\d{1,2}:\d{2}(?::\d{2})?)')
RE_LIMPIO_YT = re.compile(r'^\d{2}:\d{2}:\d{2}\s*-\s*')

TIPOS_EVENTO_SCORE = {
    'grito': 4,
    'momento_intenso': 3,
    'cambio_brusco': 2,
    'cambio_escena': 1,
    'silencio': 0
}

MODELO_MAPA = {
    "large-v3-turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
    "turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
    "large-v3": "large-v3",
    "medium": "medium",
    "small": "small",
}


def _gpu_desde_nvidia_smi() -> tuple | None:
    """Detecta GPU vía nvidia-smi sin torch. None si no hay."""
    try:
        import subprocess
        result = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            gpu_name = result.stdout.strip()
            print(f"      GPU detectada vía nvidia-smi: {gpu_name}")
            return ("cuda", "float16")
    except Exception:
        pass
    print("      No se detectó GPU, usando CPU")
    return None


def _gpu_desde_torch() -> tuple | None:
    """Detecta GPU con torch (o nvidia-smi si falta torch). None si no hay."""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            print(f"      GPU detectada: {gpu_name}")
            return ("cuda", "float16")
        print("      CUDA no disponible en torch, usando CPU")
        return None
    except ImportError:
        print("      torch no instalado, intentando detectar GPU manualmente...")
        # Fallback: verificar si hay GPU disponible sin torch
        return _gpu_desde_nvidia_smi()
    except Exception as e:
        print(f"      Error detectando GPU: {e}, usando CPU")
        return None


def detectar_device(force_gpu: bool = False) -> tuple:
    """Detecta si hay GPU disponible. En RunPod siempre hay GPU RTX."""
    # Si se fuerza GPU o estamos en RunPod (variable de entorno), intentar CUDA
    use_gpu = force_gpu or os.environ.get("RUNPOD_GPU", "").lower() in ("1", "true", "yes")

    if use_gpu:
        gpu = _gpu_desde_torch()
        if gpu is not None:
            return gpu

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


def _ts_a_hhmmss(ts: str) -> str:
    """Normaliza 'M:SS' o 'H:MM:SS' a 'HH:MM:SS'."""
    partes = ts.split(':')
    if len(partes) == 2:
        return f"00:{int(partes[0]):02d}:{int(partes[1]):02d}"
    elif len(partes) == 3:
        return f"{int(partes[0]):02d}:{int(partes[1]):02d}:{int(partes[2]):02d}"
    return "00:00:00"


def _flush_segmento_youtube(segmentos: list, timestamp_actual: str | None, texto_pendiente: str) -> None:
    """Cierra el segmento pendiente si hay timestamp y texto."""
    if texto_pendiente and timestamp_actual:
        segmentos.append((timestamp_actual, texto_pendiente.strip()))


def _abrir_segmento_limpio(linea: str, timestamp_actual: str | None, texto_pendiente: str, segmentos: list) -> tuple:
    """Línea 'HH:MM:SS - texto': cierra el pendiente y abre el nuevo."""
    _flush_segmento_youtube(segmentos, timestamp_actual, texto_pendiente)
    timestamp_actual = linea[:8]
    texto_pendiente = RE_LIMPIO_YT.sub('', linea).strip()
    return timestamp_actual, texto_pendiente


def _abrir_segmento_ts(linea: str, match, segmentos: list, timestamp_actual: str | None, texto_pendiente: str) -> tuple:
    """Línea 'M:SS texto': cierra el pendiente y abre el nuevo con timestamp normalizado."""
    _flush_segmento_youtube(segmentos, timestamp_actual, texto_pendiente)
    ts_raw = match.group(1)
    timestamp_actual = _ts_a_hhmmss(ts_raw)
    resto = linea[len(ts_raw):]
    resto = _remover_descripcion(resto.strip())
    texto_pendiente = resto
    return timestamp_actual, texto_pendiente


def _integrar_linea_youtube(
    linea: str,
    timestamp_actual: str | None,
    texto_pendiente: str,
    segmentos: list,
) -> tuple:
    """Procesa una línea cruda de YouTube y actualiza el estado del parseo."""
    if RE_LIMPIO_YT.match(linea):
        return _abrir_segmento_limpio(linea, timestamp_actual, texto_pendiente, segmentos)

    match = RE_TS_YT.match(linea)
    if match:
        return _abrir_segmento_ts(linea, match, segmentos, timestamp_actual, texto_pendiente)

    if texto_pendiente:
        texto_pendiente += " " + linea
    return timestamp_actual, texto_pendiente


def _escribir_segmentos_youtube(salida: str, segmentos: list) -> None:
    """Escribe los segmentos como 'HH:MM:SS - texto', omitiendo textos vacíos."""
    with open(salida, 'w', encoding='utf-8') as f:
        for ts, texto in segmentos:
            if texto:
                f.write(f"{ts} - {texto}\n")


def _log_segmentos_parseados(segmentos: list) -> None:
    """Resumen de segmentos parseados y muestra de los primeros 3."""
    print(f"      ✓ {len(segmentos)} segmentos parseados")
    if segmentos:
        print(f"      Rango: {segmentos[0][0]} → {segmentos[-1][0]}")
        print(f"      Verificación - primeros 3 segmentos:")
        for ts, txt in segmentos[:3]:
            print(f"        {ts}: {txt[:70]}")


def _aviso_ts_inicial(primer_ts: str) -> None:
    """Avisa si el primer timestamp del parseo no arranca en 00:00:00."""
    if primer_ts != "00:00:00":
        print(f"      AVISO: Primer timestamp es {primer_ts}, esperado 00:00:00")


def _aviso_texto_numerico(primer_texto: str) -> None:
    """Avisa si el primer texto del parseo empieza con un dígito."""
    if primer_texto and primer_texto[0].isdigit():
        print(f"      AVISO: Primer texto empieza con número: '{primer_texto[:30]}'")


def _avisos_primer_segmento(segmentos: list) -> None:
    """Validaciones de sanidad sobre el primer segmento parseado."""
    if not segmentos:
        return
    primer_ts = segmentos[0][0]
    primer_texto = segmentos[0][1]
    _aviso_ts_inicial(primer_ts)
    _aviso_texto_numerico(primer_texto)


def parsear_transcripcion_youtube(
    ruta: str,
    salida: str = "transcripcion_formatted.txt"
) -> str:
    """Parsea transcripción cruda de YouTube al formato HH:MM:SS - Texto."""
    print("[3/6] Parseando transcripción de YouTube...")

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read().strip()

    lineas = contenido.split('\n')
    segmentos = []
    timestamp_actual = None
    texto_pendiente = ""

    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        timestamp_actual, texto_pendiente = _integrar_linea_youtube(
            linea, timestamp_actual, texto_pendiente, segmentos
        )

    _flush_segmento_youtube(segmentos, timestamp_actual, texto_pendiente)

    _escribir_segmentos_youtube(salida, segmentos)

    _log_segmentos_parseados(segmentos)

    _avisos_primer_segmento(segmentos)

    print(f"      Guardado: {salida}")

    return salida


def _importar_faster_whisper():
    """Importa faster_whisper o aborta con mensaje de instalación."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "faster-whisper no instalado.\n"
            "Instalar: pip install faster-whisper"
        )
    return WhisperModel


# Cache HF persistente de RunPod; el fallback efímero mantiene el worker usable
# en local, tests y endpoints que no tengan Network Volume.
_CACHE_HF_VOLUMEN = "/runpod-volume/hf_cache"
_CACHE_HF_DEFAULT = "/tmp/cache/huggingface"
_WHISPER_MODEL_LOCK = threading.RLock()
_WHISPER_MODEL_INSTANCES: dict[tuple[str, str, str, str], object] = {}


def _volume_utilizable(ruta: str) -> bool:
    """True si el mount existe y permite crear/escribir el cache HF."""
    padre = os.path.dirname(ruta)
    if os.path.isdir(ruta):
        return os.access(ruta, os.W_OK)
    if not os.path.isdir(padre) or not os.access(padre, os.W_OK):
        return False
    try:
        os.makedirs(ruta, exist_ok=True)
    except OSError:
        return False
    return os.access(ruta, os.W_OK)


def _directorio_cache_hf() -> str:
    """Selecciona cache persistente o /tmp y alinea las variables de HF."""
    cache_home = _CACHE_HF_VOLUMEN if _volume_utilizable(_CACHE_HF_VOLUMEN) else _CACHE_HF_DEFAULT
    hub_cache = os.path.join(cache_home, "hub")
    try:
        os.makedirs(hub_cache, exist_ok=True)
    except OSError:  # HF intentará crearla; mantiene el fallback para compatibilidad
        pass
    os.environ["HF_HOME"] = cache_home
    os.environ["HUGGINGFACE_HUB_CACHE"] = hub_cache
    return hub_cache


def _resolver_modelo(modelo: str) -> tuple:
    """(model_id, download_root) según el modelo pedido y el cache HF activo."""
    model_name = MODELO_MAPA.get(modelo, "deepdml/faster-whisper-large-v3-turbo-ct2")
    local_model = os.environ.get("WHISPER_MODEL_PATH", "").strip()
    if local_model and Path(local_model).is_dir():
        return local_model, _directorio_cache_hf()
    return model_name, _directorio_cache_hf()


def _snapshot_cacheado(model_id: str, cache_root: str) -> str | None:
    """Ruta de snapshot usable para evitar cualquier descarga del repo cacheado."""
    if Path(model_id).is_dir():
        return model_id
    repo_cache = Path(cache_root) / f"models--{model_id.replace('/', '--')}"
    snapshots = repo_cache / "snapshots"
    try:
        revision = (repo_cache / "refs" / "main").read_text(encoding="utf-8").strip()
        candidates = [snapshots / revision]
    except OSError:
        candidates = []
    if snapshots.is_dir():
        candidates.extend(path for path in snapshots.iterdir() if path not in candidates)
    return next((str(path) for path in candidates if (path / "model.bin").is_file()), None)


def _modelo_desde_cache(model_id: str, cache_root: str) -> tuple[str, bool]:
    """Resuelve hit/miss sobre la ruta realmente usada por faster-whisper."""
    snapshot = _snapshot_cacheado(model_id, cache_root)
    if snapshot:
        print(f"[Whisper] Cache hit en disco: {snapshot}")
        return snapshot, True
    print(f"[Whisper] Cache miss: {model_id}; se descargará al cache configurado.")
    return model_id, False


def _crear_modelo_whisper(model_id: str, device: str, compute_type: str, download_root: str, local_files_only: bool):
    """Construye una instancia Whisper para el proceso warm actual."""
    WhisperModel = _importar_faster_whisper()
    return WhisperModel(
        model_id,
        device=device,
        compute_type=compute_type,
        download_root=download_root,
        local_files_only=local_files_only,
    )


def _cargar_modelo_whisper(model_name: str, device: str, compute_type: str, cache_root: str):
    """Carga desde disco o reutiliza instancia en memoria y mide el tiempo."""
    key = (model_name, device, compute_type, cache_root)
    with _WHISPER_MODEL_LOCK:
        if key in _WHISPER_MODEL_INSTANCES:
            print("[Whisper] Modelo hit en memoria; reutilizando instancia warm.")
            return _WHISPER_MODEL_INSTANCES[key]
        _WHISPER_MODEL_INSTANCES.clear()
        resolved_model, cached = _modelo_desde_cache(model_name, cache_root)
        started = time.perf_counter()
        try:
            model = _crear_modelo_whisper(resolved_model, device, compute_type, cache_root, cached)
        except Exception:
            print(f"[Whisper] Falló carga del modelo tras {time.perf_counter() - started:.3f}s")
            raise
        _WHISPER_MODEL_INSTANCES[key] = model
        elapsed = time.perf_counter() - started
    state = "hit en disco" if cached else "miss"
    print(f"[Whisper] Modelo {state}; carga={elapsed:.3f}s; device={device}")
    return model


def _transcribir_segmentos(model, audio_path: str, idioma: str, salida: str) -> str:
    """Corre la transcripción, muestra progreso y escribe el archivo formateado."""
    print(f"      Transcribiendo...")
    segments_gen, info = model.transcribe(
        audio_path,
        language=idioma,
        # word_timestamps=True (issue #115): el pipeline genera timestamps por
        # palabra; el formato de salida 'HH:MM:SS - texto' queda idéntico.
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
        temperature=0.0,
    )

    duracion_total = info.duration
    segmentos_texto = []
    ultimo_tiempo = 0.0

    print(f"      Duración: {duracion_total:.0f}s")
    print(f"      [{'░' * 40}] 0%", end='', flush=True)

    inicio = time.time()

    for segment in segments_gen:
        segmentos_texto.append({
            "ts": segundos_a_ms(segment.start),
            "texto": segment.text.strip()
        })
        ultimo_tiempo = segment.end

        progreso = min(ultimo_tiempo / duracion_total, 1.0)
        pct = int(progreso * 100)
        llenos = int(progreso * 40)
        barra = '█' * llenos + '░' * (40 - llenos)

        transcurrido = time.time() - inicio
        velocidad = ultimo_tiempo / max(transcurrido, 0.1)
        eta = int((duracion_total - ultimo_tiempo) / max(velocidad, 0.1))

        print(
            f"\r      [{barra}] {pct}% | {velocidad:.1f}x | {eta}s restantes    ",
            end='', flush=True
        )

    print(f"\r      [{'█'*40}] 100% ✓                              ")

    with open(salida, 'w', encoding='utf-8') as f:
        for seg in segmentos_texto:
            if seg['texto']:
                f.write(f"{seg['ts']} - {seg['texto']}\n")

    print(f"      ✓ {len(segmentos_texto)} segmentos transcritos")
    print(f"      Guardado: {salida}")

    return salida


def transcribir_audio(
    audio_path: str,
    salida: str = "transcripcion_formatted.txt",
    modelo: str = "large-v3-turbo",
    idioma: str = "es",
) -> str:
    """Transcribe audio WAV con faster-whisper y genera transcripcion_formatted.txt."""
    print(f"[Whisper] Transcribiendo audio: {audio_path}")

    # Forzar GPU en RunPod (siempre tiene GPU RTX)
    device, compute_type = detectar_device(force_gpu=True)
    print(f"      Device: {device} ({compute_type})")

    model_id, cache_root = _resolver_modelo(modelo)

    try:
        model = _cargar_modelo_whisper(model_id, device, compute_type, cache_root)

        return _transcribir_segmentos(model, audio_path, idioma, salida)

    except Exception as e:
        raise RuntimeError(f"Error transcribiendo con Whisper: {e}")


def transcribir_video(
    video_path: str,
    salida: str = "transcripcion_formatted.txt",
    modelo: str = "large-v3-turbo",
    idioma: str = "es",
) -> str:
    """Transcribe video con faster-whisper y genera transcripcion_formatted.txt."""
    print("[3/6] Transcribiendo con faster-whisper...")
    print(f"      Modelo: {modelo}")
    print(f"      Estimación: ~5-6 min para video de 11min en CPU")

    # Forzar GPU en RunPod (siempre tiene GPU RTX)
    device, compute_type = detectar_device(force_gpu=True)
    print(f"      Device: {device} ({compute_type})")

    model_id, cache_root = _resolver_modelo(modelo)

    audio_temp = _extraer_audio(video_path)

    try:
        model = _cargar_modelo_whisper(model_id, device, compute_type, cache_root)

        _transcribir_segmentos(model, audio_temp, idioma, salida)

    finally:
        try:
            os.remove(audio_temp)
        except:
            pass

    return salida


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Uso:")
        print("  Con transcripción: python whisper_transcriber.py transcripcion.txt")
        print("  Con video:         python whisper_transcriber.py video.mp4")
        sys.exit(1)
    
    entrada = sys.argv[1]
    salida = sys.argv[2] if len(sys.argv) > 2 else "transcripcion_formatted.txt"
    
    if entrada.endswith('.txt'):
        parsear_transcripcion_youtube(entrada, salida)
    else:
        transcribir_video(entrada, salida)
