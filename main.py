#!/usr/bin/env python3
"""
Generador automático de clips virales.
Extracción de audio + análisis automático + IA + recorte.
"""

import os
import re
import json
import time
import subprocess
import sys
import shutil

# Forzar la codificación de la consola a UTF-8 en Windows para evitar errores
# al imprimir caracteres especiales (✓, ►, etc.) en PowerShell
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import logging

import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from audio_analyzer import analizar_audio, guardar_json
    AUDIO_ANALYZER_AVAILABLE = True
except ImportError:
    AUDIO_ANALYZER_AVAILABLE = False


def _parsear_linea_env(linea: str) -> Optional[tuple]:
    """Parsea una línea de .env. None si está vacía, es comentario o no tiene '='."""
    linea = linea.strip()
    if not linea or linea.startswith("#") or "=" not in linea:
        return None
    clave, _, valor = linea.partition("=")
    return clave.strip(), valor.strip().strip('"').strip("'")


def _guardar_env_var(clave: str, valor: str) -> None:
    """Define la variable solo si la clave es válida y no existe aún."""
    if clave and clave not in os.environ:
        os.environ[clave] = valor


def cargar_env(ruta: str = ".env") -> None:
    """Carga variables de entorno desde un archivo .env si existe."""
    if not os.path.exists(ruta):
        return
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            parseada = _parsear_linea_env(linea)
            if parseada is not None:
                _guardar_env_var(*parseada)


cargar_env()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
ANTHROPIC_FALLBACK_MODEL = os.environ.get("ANTHROPIC_FALLBACK_MODEL", "claude-haiku-5-5")
ANTHROPIC_VERSION = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")
ANTHROPIC_WORKSPACE_ID = os.environ.get("ANTHROPIC_WORKSPACE_ID", "")
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_ENDPOINT = os.environ.get("OPENROUTER_ENDPOINT", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", os.environ.get("OPENAI_MODEL", "anthropic/claude-3.5-sonnet"))
API_ENDPOINT = os.environ.get("API_ENDPOINT", "https://api.deepseek.com/v1/chat/completions")
MODEL = os.environ.get("MODEL", "deepseek-chat")
TIMEOUT = 180
MAX_INTENTOS = 3


def verificar_ffmpeg() -> bool:
    """Verifica si FFmpeg está instalado."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def verificar_dependencias() -> bool:
    """Verifica que las dependencias estén instaladas."""
    if not PYDUB_AVAILABLE:
        print("Error: pydub no está instalado")
        print("Ejecuta: pip install pydub")
        return False
    return True


def extraer_audio(video_path: str, audio_path: str = "audio.mp3") -> str:
    """Extrae el audio de un video usando FFmpeg."""
    print("[1/6] Extrayendo audio del video...")
    
    if os.path.exists(audio_path):
        os.remove(audio_path)
    
    comando = [
        "ffmpeg", "-y", "-i", video_path,
        "-q:a", "0", "-map", "a", audio_path
    ]
    
    try:
        subprocess.run(comando, capture_output=True, check=True)
        print(f"      Audio guardado: {audio_path}")
        return audio_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error al extraer audio: {e.stderr.decode()}")


def _agregar_momentos_cluster(eventos: List[Dict]) -> None:
    """Agrega los momentos virales del clustering (momentos_virales.json) a los eventos."""
    if os.path.exists("momentos_virales.json"):
        with open("momentos_virales.json", "r", encoding="utf-8") as f:
            momentos = json.load(f)
        if momentos and "momentos" in momentos:
            eventos_cluster = momentos["momentos"]
            print(f"      Momentos virales del clustering: {len(eventos_cluster)}")

            for mc in eventos_cluster[:5]:
                eventos.append({
                    "timestamp": mc.get("timestamp", "0:00"),
                    "intensidad": mc.get("intensidad", 7.0),
                    "tipo": "momento_viral",
                    "score_ia": mc.get("score_ia", 8),
                    "criterio": mc.get("criterio_principal", "viral"),
                })


def _eventos_top_ordenados(eventos: List[Dict]) -> List[Dict]:
    """Ordena por intensidad desc, toma top 50 y ordena por timestamp."""
    eventos = sorted(eventos, key=lambda x: x.get("intensidad", 0), reverse=True)
    eventos_top = eventos[:50]
    eventos_top = sorted(eventos_top, key=lambda x: x.get("timestamp", ""))
    return eventos_top


def analizar_audio_video(audio_path: str = "audio.mp3", max_eventos: int = 30) -> List[Dict]:
    """Analiza el audio usando el módulo audio_analyzer."""
    print("[2/6] Analizando audio...")

    if not AUDIO_ANALYZER_AVAILABLE:
        print("      audio_analyzer no disponible")
        return []

    try:
        eventos = analizar_audio(audio_path, "audio.json")
        _agregar_momentos_cluster(eventos)

        eventos_top = _eventos_top_ordenados(eventos)

        print(f"      Eventos detectados: {len(eventos)}, usando top {len(eventos_top)}")
        return eventos_top
    except Exception as e:
        print(f"      Error en análisis: {e}")
        return []


def leer_transcripcion_completa(ruta: str) -> str:
    """Lee el archivo completo sin límite. Usar para formatear_transcripcion()."""
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read().strip()


def leer_transcripcion_para_ia(ruta: str, max_chars: int = 6000) -> str:
    """Lee con límite de chars. Usar solo para construir el prompt de la IA."""
    with open(ruta, "r", encoding="utf-8") as f:
        contenido = f.read().strip()
    if len(contenido) > max_chars:
        contenido = contenido[:max_chars].rsplit('\n', 1)[0]
        print(f"      Transcripción truncada para IA: {len(contenido)} caracteres")
    return contenido


def leer_transcripcion(ruta: str, max_chars: int = 8000) -> str:
    """Lee el archivo de transcripción (deprecated, usar leer_transcripcion_completa o leer_transcripcion_para_ia)."""
    return leer_transcripcion_completa(ruta)


RE_TS = re.compile(r'^(\d{1,2}:\d{2}(?::\d{2})?)')
RE_SEG = re.compile(r'^\d+\s+(segundo|minuto|hora)s?', re.IGNORECASE)
RE_MIN = re.compile(r'^\d+\s+minutos?\s+y\s+\d+\s+segundos?', re.IGNORECASE)


def _flush_segmento(segmentos: list, timestamp_actual: Optional[str], texto_pendiente: str) -> None:
    """Agrega el segmento pendiente a la lista si hay timestamp y texto."""
    if texto_pendiente and timestamp_actual:
        h, m, s = _parse_timestamp(timestamp_actual)
        segmentos.append((f"{h:02d}:{m:02d}:{s:02d}", texto_pendiente))


def _texto_restante_de_linea(linea: str, match_ts) -> str:
    """Texto que sigue al timestamp de la línea, sin rótulos de segundos/minutos."""
    texto_restante = linea[len(match_ts.group(0)):].strip()
    texto_restante = RE_SEG.sub('', texto_restante)
    texto_restante = RE_MIN.sub('', texto_restante)
    return texto_restante


def _integrar_linea_transcripcion(
    linea: str,
    match_ts,
    timestamp_actual: Optional[str],
    texto_pendiente: str,
    segmentos: list,
) -> tuple:
    """Procesa una línea: abre un nuevo segmento o acumula texto en el pendiente."""
    if match_ts:
        _flush_segmento(segmentos, timestamp_actual, texto_pendiente)
        return match_ts.group(1), _texto_restante_de_linea(linea, match_ts)
    if texto_pendiente:
        texto_pendiente += " " + linea
    return timestamp_actual, texto_pendiente


def _segmentos_de_transcripcion_raw(lineas_raw: list) -> list:
    """Recorre las líneas crudas y arma la lista de (ts, texto)."""
    segmentos = []
    texto_pendiente = ""
    timestamp_actual = None

    for linea in lineas_raw:
        linea = linea.strip()
        if not linea:
            continue
        match_ts = RE_TS.match(linea)
        timestamp_actual, texto_pendiente = _integrar_linea_transcripcion(
            linea, match_ts, timestamp_actual, texto_pendiente, segmentos
        )

    _flush_segmento(segmentos, timestamp_actual, texto_pendiente)
    return segmentos


def _escribir_transcripcion_formateada(salida_path: str, segmentos: list) -> None:
    """Escribe el archivo formateado y muestra el resumen por consola."""
    with open(salida_path, "w", encoding="utf-8") as f:
        for ts, texto in segmentos:
            f.write(f"{ts} - {texto}\n")

    ts_primero = segmentos[0][0]
    ts_ultimo = segmentos[-1][0]
    print(f"      ✓ Transcripción formateada: {salida_path} ({len(segmentos)} segmentos)")
    print(f"      Rango: {ts_primero} hasta {ts_ultimo}")
    for i, (ts, txt) in enumerate(segmentos[:5]):
        print(f"        {ts}: {txt[:50]}...")


def formatear_transcripcion(transcripcion_raw: str, salida_path: str = "transcripcion_formatted.txt") -> str:
    """
    Convierte la transcripción cruda de YouTube al formato HH:MM:SS - Texto
    SIN modificar los timestamps ni el texto. Solo limpia y reformatea.
    Procesa TODAS las líneas sin límite.
    """
    print("[3.5/6] Formateando transcripción completa...")

    lineas_raw = transcripcion_raw.strip().split('\n')
    segmentos = _segmentos_de_transcripcion_raw(lineas_raw)

    if not segmentos:
        print("      ✗ No se pudieron parsear segmentos")
        return transcripcion_raw

    _escribir_transcripcion_formateada(salida_path, segmentos)

    return salida_path


def _parse_timestamp(ts: str) -> tuple:
    """Convierte timestamp M:SS o H:MM:SS a (h, m, s)."""
    partes = ts.split(':')
    if len(partes) == 2:
        return (0, int(partes[0]), int(partes[1]))
    elif len(partes) == 3:
        return (int(partes[0]), int(partes[1]), int(partes[2]))
    return (0, 0, 0)


def _leer_segmentos_formateados(ruta: str) -> list:
    """Lee el archivo formateado y devuelve la lista de (ts, texto)."""
    with open(ruta, "r", encoding="utf-8") as f:
        lineas = [l.strip() for l in f.readlines() if l.strip()]

    segmentos = []
    for linea in lineas:
        if " - " in linea:
            partes = linea.split(" - ", 1)
            ts = partes[0].strip()
            texto = partes[1].strip()
            segmentos.append((ts, texto))
    return segmentos


def _serializar_segmentos(segmentos: list) -> str:
    """Une los segmentos como líneas 'ts - texto'."""
    return "\n".join([f"{ts} - {texto}" for ts, texto in segmentos])


def _comprimir_segmentos(segmentos: list, max_segmentos: int) -> list:
    """Muestrea los segmentos con paso fijo combinando los textos intermedios."""
    total_segmentos = len(segmentos)
    factor = total_segmentos / max_segmentos
    paso = int(factor)
    if paso < 1:
        paso = 1

    segmentos_comprimidos = []
    for i in range(0, total_segmentos, paso):
        ts, texto = segmentos[i]
        texto = _unir_textos_consecutivos(segmentos, i, paso, total_segmentos)
        segmentos_comprimidos.append((ts, texto))
    return segmentos_comprimidos


def _unir_textos_consecutivos(segmentos: list, i: int, paso: int, total_segmentos: int) -> str:
    """Junta el texto del segmento i con los siguientes hasta completar el paso."""
    ts, texto = segmentos[i]
    if i + paso < total_segmentos:
        textos_combined = [texto]
        for j in range(i + 1, min(i + paso, total_segmentos)):
            textos_combined.append(segmentos[j][1])
        texto = " ".join(textos_combined)
    return texto


def preparar_transcripcion_para_ia(ruta: str = "transcripcion_formatted.txt", max_segmentos: int = 150) -> str:
    """
    Comprime la transcripción para la IA mientras preserva todos los timestamps.
    Mantiene estructura completa pero elimina redundancias.
    """
    print("[3.8/6] Preparando transcripción para IA...")

    segmentos = _leer_segmentos_formateados(ruta)

    if not segmentos:
        return ""

    total_segmentos = len(segmentos)
    print(f"      Total segmentos: {total_segmentos}")

    if total_segmentos <= max_segmentos:
        print(f"      Sin comprimir (≤{max_segmentos} segmentos)")
        return _serializar_segmentos(segmentos)

    segmentos_comprimidos = _comprimir_segmentos(segmentos, max_segmentos)
    factor = total_segmentos / max_segmentos
    print(f"      Comprimida: {len(segmentos_comprimidos)} segmentos (factor {factor:.1f}x)")

    return _serializar_segmentos(segmentos_comprimidos)


def _ts_a_segundos(ts: str) -> float:
    """Convierte 'H:MM:SS' o 'MM:SS' a segundos (0.0 si no parsea)."""
    partes = ts.split(":")
    if len(partes) == 3:
        return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])
    elif len(partes) == 2:
        return int(partes[0]) * 60 + int(partes[1])
    return 0.0


def _segmentos_ts_desde_lineas(lineas: List[str]) -> list:
    """Convierte líneas 'ts - texto' en tuplas (ts, texto)."""
    segmentos_ts = []
    for linea in _lineas_con_ts(lineas):
        partes = linea.split(" - ", 1)
        ts = partes[0].strip()
        texto = partes[1].strip()
        segmentos_ts.append((ts, texto))
    return segmentos_ts


def _lineas_con_ts(lineas: List[str]) -> List[str]:
    """Filtra y limpia las líneas que traen timestamp."""
    return [l.strip() for l in lineas if l.strip() and " - " in l]


def _segmentos_ts_desde_archivo(transcripcion_path: str) -> list:
    """Lee el archivo de transcripción y devuelve los segmentos (ts, texto)."""
    with open(transcripcion_path, "r", encoding="utf-8") as f:
        return _segmentos_ts_desde_lineas(f.readlines())


def _segmento_mas_cercano(seg_evento: float, segmentos_ts: list) -> tuple:
    """Devuelve (segmento, distancia) del segmento más próximo al evento."""
    mejor_segmento = None
    mejor_distancia = float("inf")

    for ts, texto in segmentos_ts:
        seg_ts = _ts_a_segundos(ts)
        distancia = abs(seg_evento - seg_ts)
        if distancia < mejor_distancia:
            mejor_distancia = distancia
            mejor_segmento = (ts, texto)
    return mejor_segmento, mejor_distancia


def _enriquecer_evento(evento: Dict, segmentos_ts: list) -> Optional[Dict]:
    """Correlaciona un evento de audio con la transcripción. None si no hay match."""
    ts_evento = evento.get("timestamp", "0:00")
    seg_evento = _ts_a_segundos(ts_evento)

    mejor_segmento, mejor_distancia = _segmento_mas_cercano(seg_evento, segmentos_ts)

    if mejor_segmento and mejor_distancia < 30:
        return {
            "timestamp": ts_evento,
            "intensidad": evento.get("intensidad", 5),
            "tipo": evento.get("tipo", "evento"),
            "texto_correlacionado": mejor_segmento[1][:200],
            "timestamp_transcripcion": mejor_segmento[0],
            "distancia_segundos": mejor_distancia,
        }
    return None


def enriquecer_datos_para_ia(datos_audio: List[Dict], transcripcion_path: str = "transcripcion_formatted.txt") -> Dict:
    """
    Correlaciona eventos de audio con segmentos de transcripción.
    Returns un diccionario con datos enriquecidos para la IA.
    """
    print("[3.9/6] Enriqueciendo datos para IA...")

    segmentos_ts = _segmentos_ts_desde_archivo(transcripcion_path)

    eventos_enriquecidos = []

    for evento in datos_audio:
        enriquecido = _enriquecer_evento(evento, segmentos_ts)
        if enriquecido is not None:
            eventos_enriquecidos.append(enriquecido)

    print(f"      Eventos enriquecidos: {len(eventos_enriquecidos)}")

    return {
        "eventos": eventos_enriquecidos,
        "total_segmentos": len(segmentos_ts),
        "correlacion_exitosa": len(eventos_enriquecidos),
    }


def construir_prompt(transcripcion: str, datos_audio: List[Dict], datos_enriquecidos: Dict = None) -> str:
    """Construye el prompt para la IA."""
    
    if datos_enriquecidos and datos_enriquecidos.get("eventos"):
        audio_json = json.dumps(datos_enriquecidos["eventos"], indent=2, ensure_ascii=False)
    else:
        audio_json = json.dumps(datos_audio, indent=2, ensure_ascii=False)
    
    return f"""Sos un experto en crear contenido viral para redes sociales (TikTok, Reels, Shorts). Tu objetivo es encontrar los momentos más interesantes, emocionantes, polémicos, educativos o informativos de CUALQUIER tipo de video. No importa si es deporte, entrevista, vlog, tutorial, gaming, música, noticias o cualquier otro género. Buscá los segmentos que más enganchen a la audiencia.

DEVOLVÉ ÚNICAMENTE UN ARRAY JSON VÁLIDO. Sin texto antes ni después. Sin markdown. Empezá con [ y terminá con ].

REGLA OBLIGATORIA: Debés devolver SIEMPRE un array con entre 1 y 5 clips. Si no hay momentos perfectos, elegí los mejores segmentos disponibles como 'mejor esfuerzo'. NUNCA devuelvas un array vacío [].

CRITERIOS DE VIRALIDAD (ordenados por peso):

REVELACIÓN O EXCLUSIVA (peso 10/10)
Información que el espectador no sabía y genera sorpresa. Datos internos, rumores confirmados, primicias. Frases como "tengo la información", "me dijeron", "la verdad es que".

CONTROVERSIA O CONTRADICCIÓN (peso 9/10)
Momentos donde se contradice la versión oficial. Críticas directas. Predicciones arriesgadas con fundamento. Frases como "no puede ser", "me parece mal", "error garrafal".

DATO CONCRETO IMPACTANTE (peso 8/10)
Números, fechas, montos específicos que sorprenden. Comparaciones que reencuadran la realidad.

MOMENTO EMOCIONAL AUTÉNTICO (peso 7/10)
Nostalgia, pasión, anécdota personal. Momento donde alguien se quiebra o se emociona.

ANÁLISIS TÉCNICO SIMPLE Y CLARO (peso 6/10)
Explicación de por qué pasó algo de manera accesible. Máximo cuando usa metáforas o ejemplos concretos.

PREDICCIÓN O ANTICIPACIÓN (peso 5/10)
Se adelanta algo que va a pasar. Spoiler de una decisión futura. Genera curiosidad sobre si acertó o no.

SEÑALES DE AUDIO QUE AMPLIFICAN EL SCORE:
- intensidad > 7.0 en el timestamp: +1 punto al score
- evento "cambio_brusco" cerca del inicio del clip: +0.5 puntos
- evento "momento_intenso" sostenido: +1 punto
- intensidad < 4.0 (pausa dramática antes del clip): +0.5 puntos

REGLAS PARA DEFINIR INICIO Y FIN DE CADA CLIP:

INICIO del clip:
- OBLIGATORIO: empezar 3-4 segundos ANTES de la frase clave para dar contexto completo
- Nunca cortar en medio de una oración
- Preferir iniciar después de una pausa natural (silencio en datos de audio)
- El primer segundo debe enganchar: pregunta, dato impactante o afirmación fuerte

FIN del clip:
- OBLIGATORIO: terminar 3-4 segundos DESPUÉS de que cierre la idea
- Terminar en punto final de idea (punto, no coma), nunca a mitad de frase
- Ideal: terminar con conclusión, frase de impacto, o transición natural
- Dejar al espectador con ganas de saber más (cliffhanger) cuando sea posible
- OBLIGATORIO: clips de 30-90 segundos (mínimo 30, máximo 90)
- El punto óptimo es 45-70 segundos para TikTok/Reels

EVITAR:
- Clips que empiezan con "y", "pero", "entonces" sin contexto previo
- Clips que cortan la idea a la mitad (debe cerrar la idea completamente)
- Dos clips con el mismo tema o personaje
- Clips de más de 80 segundos salvo que sea una revelación excepcional

DATOS DE AUDIO DEL VIDEO:
{audio_json}

Instrucciones para usar los datos de audio:
- Buscá timestamps con intensidad >= 7.5: son momentos de alta energía vocal
- Los eventos "cambio_brusco" marcan transiciones abruptas de tema
- Los eventos "momento_intenso" indican energía sostenida (bueno para clips)
- Correlacioná los timestamps del audio con los timestamps de la transcripción para validar que los clips propuestos coincidan con momentos de energía alta

TRANSCRIPCIÓN COMPLETA:
{transcripcion}

FORMATO JSON DE SALIDA OBLIGATORIO:
REGLAS OBLIGATORIAS DE DURACIÓN:
- CADA clip debe durar entre 30 y 90 SEGUNDOS
- NO ACCEPTAR clips menores a 30 segundos
- NO ACCEPTAR clips mayores a 90 segundos
- La duración se calcula como: fin - inicio
- Si un clip dura menos de 30s, NO ES VÁLIDO - debes extenderlo
- La IA debe asegurar que cada clip propuesto cumpla 30-90s
[
{{
"inicio": "HH:MM:SS",
"fin": "HH:MM:SS",
"duracion": 35,
"score": 9,
"criterio_principal": "revelacion",
"titulo_sugerido": "La VERDAD de por qué sacaron a Bustos",
"hook_texto": "Lo que nadie te contó",
"primer_segundo": "frase exacta con la que arranca el clip",
"motivo": "explicación de por qué es viral en 1 oración",
"tipo_contenido": "exclusiva",
"audio_score": 8
}}

CAMPOS OBLIGATORIOS:
- inicio/fin: timestamps exactos en HH:MM:SS
- duracion: segundos enteros (fin - inicio)
- score: 1-10 basado en criterios de viralidad
- criterio_principal: uno de [revelacion, controversia, dato_impactante, emocional, analisis_tactico, prediccion]
- titulo_sugerido: título para el clip en español rioplatense, max 60 chars, sin clickbait vacío, con el dato concreto que engancha
- hook_texto: texto del gancho inicial (2-5 palabras), distinto para cada clip
- primer_segundo: primeras palabras exactas de la transcripción que abre el clip
- motivo: por qué este momento específico va a generar engagement
- tipo_contenido: uno de [exclusiva, analisis, emocion, prediccion, controversia]
- audio_score: 1-10 basado en los datos de audio en ese rango de tiempo

REGLAS FINALES:
- Asigná un score del 1 al 10, pero incluí todos los clips que tengan al menos un 5
- Devolvé entre 1 y 5 clips (NUNCA 0)
- No repetir el mismo tema o personaje en más de 2 clips
- El primer clip del array DEBE ser el de mayor score
- Todos los timestamps deben existir en la transcripción proporcionada
- Empezá con [ y terminá con ]"""


def _manejar_error_post(e: Exception, intento: int, intentos: int) -> None:
    """Relanza el error como TimeoutError/ConnectionError tipado si se agotaron los intentos."""
    if intento != intentos:
        return
    if isinstance(e, requests.exceptions.Timeout):
        raise TimeoutError("La solicitud excedió el tiempo de espera")
    raise ConnectionError(f"Error de conexión: {e}")


def _post_con_retry(url: str, headers: Dict, body: Dict, timeout: int = TIMEOUT, intentos: int = MAX_INTENTOS) -> requests.Response:
    """POST con reintentos automáticos ante cortes de conexión."""
    for intento in range(1, intentos + 1):
        try:
            return requests.post(url, headers=headers, json=body, timeout=timeout)
        except requests.exceptions.Timeout as e:
            _manejar_error_post(e, intento, intentos)
        except requests.exceptions.RequestException as e:
            _manejar_error_post(e, intento, intentos)
        print(f"      Intento {intento} falló, reintentando en {2 * intento}s...")
        time.sleep(2 * intento)


def _headers_claude() -> Dict:
    """Headers del request a la API de Anthropic."""
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    if ANTHROPIC_WORKSPACE_ID:
        headers["anthropic-workspace-id"] = ANTHROPIC_WORKSPACE_ID
    return headers


def _texto_de_bloques(datos: Dict) -> str:
    """Concatena los bloques de texto de la respuesta de Anthropic."""
    texto = ""
    for bloque in datos.get("content", []):
        if bloque.get("type") == "text" and bloque.get("text"):
            texto += bloque["text"]
    return texto


def llamar_claude(prompt: str) -> str:
    """Llama a la API de Anthropic Claude y devuelve el texto de la respuesta."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("Define ANTHROPIC_API_KEY en el archivo .env")

    headers = _headers_claude()
    body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 8192,
        "thinking": {"type": "between_tools"},
        "messages": [{"role": "user", "content": prompt}],
    }

    respuesta = _post_con_retry(ANTHROPIC_ENDPOINT, headers, body)
    if respuesta.status_code != 200:
        raise ConnectionError(f"Error {respuesta.status_code}: {respuesta.text[:500]}")

    datos = respuesta.json()
    texto = _texto_de_bloques(datos)
    if texto:
        return texto
    raise ValueError("Respuesta inválida de la API: sin bloque de texto")


def _clave_openai_compatible() -> str:
    """Primera clave de API disponible para proveedores estilo OpenAI."""
    return OPENAI_API_KEY or OPENROUTER_API_KEY or os.getenv("DEEPSEEK_API_KEY", "")


def _config_deepseek_o_openai() -> tuple:
    """Endpoint/modelo/clave cuando no hay clave de OpenRouter."""
    if os.getenv("DEEPSEEK_API_KEY", "") and not OPENAI_API_KEY:
        return "https://api.deepseek.com/v1/chat/completions", os.getenv("MODEL", "deepseek-chat"), os.getenv("DEEPSEEK_API_KEY", "")
    return API_ENDPOINT, MODEL, OPENAI_API_KEY


def _config_openai_compatible() -> tuple:
    """Endpoint, modelo y clave efectiva según el proveedor configurado."""
    if OPENROUTER_API_KEY:
        return OPENROUTER_ENDPOINT, OPENROUTER_MODEL, OPENROUTER_API_KEY
    return _config_deepseek_o_openai()


def _contenido_de_respuesta_openai(respuesta: requests.Response) -> str:
    """Extrae el texto de la respuesta estilo OpenAI, validando su forma."""
    try:
        datos = respuesta.json()
        return datos["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Respuesta inválida de la API: {e}")


def llamar_openai_compatible(prompt: str) -> str:
    """Llama a una API estilo OpenAI (DeepSeek/OpenRouter/u otra) y devuelve el texto."""
    key = _clave_openai_compatible()
    if not key:
        raise ValueError("Define OPENAI_API_KEY / OPENROUTER_API_KEY / DEEPSEEK_API_KEY en .env")
    endpoint, model, eff_key = _config_openai_compatible()
    headers = {
        "Authorization": f"Bearer {eff_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://clipsai.local",
        "X-Title": "ClipsAI",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }

    respuesta = _post_con_retry(endpoint, headers, body)
    if respuesta.status_code != 200:
        raise ConnectionError(f"Error {respuesta.status_code}: {respuesta.text[:500]}")

    return _contenido_de_respuesta_openai(respuesta)


def _verificar_claves_ia() -> None:
    """Valida que haya al menos una clave de API de IA configurada."""
    has_anthropic = bool(ANTHROPIC_API_KEY)
    has_openai = bool(os.getenv("OPENAI_API_KEY", ""))
    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY", ""))
    has_deepseek = bool(os.getenv("DEEPSEEK_API_KEY", ""))
    if not has_anthropic and not has_openai and not has_openrouter and not has_deepseek:
        raise ValueError(
            "Falta la clave de API para la inteligencia artificial. "
            "Por favor completa una de estas variables en tu archivo `.env`: "
            "- ANTHROPIC_API_KEY (para Claude/Anthropic)"
            "- OPENAI_API_KEY (para OpenAI)"
            "- OPENROUTER_API_KEY (para OpenRouter)"
            "- DEEPSEEK_API_KEY (para DeepSeek)"
        )


def _elegir_proveedor() -> str:
    if ANTHROPIC_API_KEY:
        return "Claude (Anthropic)"
    if OPENROUTER_API_KEY:
        return "OpenRouter"
    if OPENAI_API_KEY:
        return "OpenAI"
    return "DeepSeek"


def _llamar_proveedor_primario(prompt: str) -> str:
    """Llamada al proveedor primario según las claves disponibles."""
    if ANTHROPIC_API_KEY:
        return llamar_claude(prompt)
    return llamar_openai_compatible(prompt)


def _fallback_anthropic(prompt: str, proveedor: str) -> Optional[str]:
    """Reintenta con Claude si el primario no era Anthropic. None si no aplica o falla."""
    if not ANTHROPIC_API_KEY:
        return None
    if proveedor == "Claude (Anthropic)":
        return None
    try:
        return llamar_claude(prompt)
    except Exception:
        logger.exception("Fallback Anthropic también falló")
        return None


def _hay_fallback_openai(has_deepseek: bool) -> bool:
    """Indica si hay alguna clave de OpenAI/OpenRouter/DeepSeek para el fallback."""
    return bool(OPENROUTER_API_KEY or OPENAI_API_KEY or has_deepseek)


def _fallback_openai(prompt: str, has_deepseek: bool) -> Optional[str]:
    """Reintenta con OpenAI/OpenRouter/DeepSeek. None si no aplica o falla."""
    if not _hay_fallback_openai(has_deepseek):
        return None
    try:
        return llamar_openai_compatible(prompt)
    except Exception:
        logger.exception("Fallback OpenAI/OpenRouter/DeepSeek falló")
        return None


def _llamar_con_fallback(prompt: str, proveedor: str) -> str:
    """Llamada LLM con fallback robusto: reintenta alternativos si el primario falla."""
    has_deepseek = bool(os.getenv("DEEPSEEK_API_KEY", ""))
    try:
        return _llamar_proveedor_primario(prompt)
    except Exception:
        logger.exception("Fallo llamada LLM proveedor=%s, intentando fallback alternativo", proveedor)
    fallback = _fallback_anthropic(prompt, proveedor)
    if fallback is None:
        fallback = _fallback_openai(prompt, has_deepseek)
    if fallback is None:
        raise
    return fallback


def _es_clip_objeto(obj: dict) -> bool:
    """True si el objeto JSON trae claves 'inicio' y 'fin'."""
    return "inicio" in obj and "fin" in obj


def _clips_de_dict(data: dict) -> Optional[list]:
    """Extrae data['clips'] si es lista. None si no aplica."""
    if "clips" in data and isinstance(data["clips"], list):
        clips = data["clips"]
        print(f"      Extraidos {len(clips)} clips desde objeto con clave 'clips'")
        return clips
    return None


def _extraer_clips_de_objeto(contenido: str) -> Optional[list]:
    """Fallback 1: objeto {"clips": [...]}. None si no aplica."""
    try:
        raw = contenido.strip()
        if raw.startswith("{") and raw.endswith("}"):
            return _clips_de_dict(json.loads(raw))
    except Exception:
        pass
    return None


def _objeto_clip_tolerante(candidato: str) -> Optional[dict]:
    """Parsea un objeto suelto si trae inicio/fin. None si falla o no aplica."""
    try:
        obj = json.loads(candidato)
        if _es_clip_objeto(obj):
            return obj
    except json.JSONDecodeError:
        pass
    return None


def _objetos_sueltos_de(contenido: str) -> list:
    """Lista de objetos JSON sueltos con inicio/fin en el texto."""
    objetos = []
    for m in re.finditer(r'\{[^{}]*\}', contenido):
        obj = _objeto_clip_tolerante(m.group())
        if obj is not None:
            objetos.append(obj)
    return objetos


def _extraer_clips_de_objetos_sueltos(contenido: str) -> Optional[list]:
    """Fallback 2: parsear objetos JSON sueltos con inicio/fin."""
    objetos = _objetos_sueltos_de(contenido)
    if objetos:
        print(f"      Extraidos {len(objetos)} clips desde objetos sueltos")
        return objetos
    return None


def _clips_objetos_con_log(contenido: str) -> Optional[list]:
    """Fallback 2 con aviso en el log si el parseo de objetos falla."""
    try:
        return _extraer_clips_de_objetos_sueltos(contenido)
    except Exception as ex:
        logger.warning("Fallback parse failed: %s", ex)
        return None


def _clips_de_fallback(contenido: str) -> List[Dict]:
    """Cadena de fallbacks cuando la respuesta no trae array JSON."""
    print(f"      No se encontró array JSON. Buscando objetos individuales...")
    print(f"      Preview crudo: {contenido[:500]}...")
    clips = _extraer_clips_de_objeto(contenido)
    if clips is None:
        clips = _clips_objetos_con_log(contenido)
    if clips is None:
        raise ValueError("No se encontró JSON válido en la respuesta de la IA")
    return clips


def _extraer_json_respuesta(contenido: str) -> List[Dict]:
    """Extrae la lista de clips del texto crudo de la IA (fences, array, objetos)."""
    # 1. Si viene envuelto en markdown fences ```json ... ```, extraerlo primero
    md_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', contenido)
    if md_match:
        print(f"      Detectado JSON dentro de markdown fences")
        contenido = md_match.group(1).strip()

    # 2. Buscar el array JSON más largo posible (puede haber texto antes/después)
    json_match = re.search(r'\[[\s\S]*\]', contenido)
    if not json_match:
        # 3. Fallback: buscar objetos individuales { ... }
        return _clips_de_fallback(contenido)

    json_str = json_match.group(0)
    clips = parsear_json_tolerante(json_str)
    if not clips:
        print(f"      JSON parse devolvió 0 clips. Respuesta raw:")
        print(contenido[:2000])
        raise ValueError("No se pudo parsear la respuesta como JSON")

    print(f"      IA detectó {len(clips)} momentos")
    return clips


def obtener_clips_ia(transcripcion: str, datos_audio: List[Dict], datos_enriquecidos: Dict = None) -> List[Dict]:
    """Envía datos a la IA y retorna los clips detectados. Fallback robusto con logger."""
    _verificar_claves_ia()
    proveedor = _elegir_proveedor()
    print(f"[4/6] Analizando con IA ({proveedor})...")

    print(f"[DEBUG CLAUDE] Transcripción enviada ({len(transcripcion)} chars): {transcripcion[:300]}...")

    prompt = construir_prompt(transcripcion, datos_audio, datos_enriquecidos)
    contenido = _llamar_con_fallback(prompt, proveedor)

    print(f"      Respuesta IA ({len(contenido)} chars)")
    print(f"      === RESPUESTA COMPLETA ===")
    print(contenido[:2000])
    print(f"      === FIN RESPUESTA ===")

    # Loggear respuesta cruda completa para debug
    logger.info("Respuesta Claude raw (completa): %s", contenido)
    print(f"[DEBUG CLAUDE] Respuesta cruda recibida ({len(contenido)} chars): {contenido[:500]}...")

    return _extraer_json_respuesta(contenido)


def timestamp_a_segundos(timestamp: str) -> float:
    """Convierte timestamp a segundos (maneja HH:MM:SS, MM:SS, o segundos)."""
    timestamp = str(timestamp).strip()
    
    try:
        if ':' in timestamp:
            partes = timestamp.split(':')
            if len(partes) == 2:
                return int(partes[0]) * 60 + float(partes[1])
            elif len(partes) == 3:
                return int(partes[0]) * 3600 + int(partes[1]) * 60 + float(partes[2])
        else:
            return float(timestamp)
    except ValueError:
        return 0.0
    
    return 0.0


def reparar_json(texto: str) -> str:
    """Intenta reparar JSON común malformado."""
    texto = texto.strip()
    
    texto = re.sub(r"(\w+)\s*:\s*", r'"\1": ', texto)
    
    texto = re.sub(r":\s*'([^']*)'", r': "\1"', texto)
    
    texto = re.sub(r",(\s*[}\]])", r'\1', texto)
    
    texto = re.sub(r"(\d+)\s+(\d+:)", r'\1,\2', texto)
    
    return texto


def _rango_json(texto: str) -> str:
    """Deja el texto solo con el contenido entre el primer '[' y el último ']'."""
    md_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', texto)
    if md_match:
        texto = md_match.group(1).strip()

    first_bracket = texto.find('[')
    last_bracket = texto.rfind(']')

    if first_bracket == -1 or last_bracket == -1:
        return texto
    return texto[first_bracket:last_bracket+1]


def _intentar_parseo_json(json_str: str) -> Optional[List[Dict]]:
    """json.loads directo. None si el JSON es inválido."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def _intentar_parseo_reparado(json_str: str) -> Optional[List[Dict]]:
    """json.loads sobre el texto reparado. None si sigue inválido."""
    try:
        reparado = reparar_json(json_str)
        return json.loads(reparado)
    except json.JSONDecodeError:
        return None


def _objetos_con_inicio_fin(json_str: str) -> List[Dict]:
    """Lista de objetos sueltos con inicio/fin; [] si el barrido falla."""
    try:
        objetos = []
        for match in re.finditer(r'\{[^{}]*\}', json_str):
            obj = _objeto_clip_tolerante(match.group())
            if obj is not None:
                objetos.append(obj)
        return objetos
    except:
        return []


def parsear_json_tolerante(texto: str) -> List[Dict]:
    """Intenta parsear JSON, intentando reparar errores comunes."""
    texto = texto.strip()

    json_str = _rango_json(texto)

    clips = _intentar_parseo_json(json_str)
    if clips is not None:
        return clips

    clips = _intentar_parseo_reparado(json_str)
    if clips is not None:
        return clips

    return _objetos_con_inicio_fin(json_str)
    """Convierte segundos a HH:MM:SS."""
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    segs = segundos % 60
    return f"{horas:02d}:{minutos:02d}:{segs:02d}"


def _convertir_ts_simple(ts: str) -> int:
    """Convierte 'MM:SS' o 'HH:MM:SS' a segundos enteros (0 si no aplica)."""
    partes = ts.split(':')
    if len(partes) == 2:
        return int(partes[0]) * 60 + int(partes[1])
    elif len(partes) == 3:
        return int(partes[0]) * 3600 + int(partes[1]) * 60 + int(partes[2])
    return 0


def _formatear_ts_hhmmss(segundos: float) -> str:
    """Convierte segundos a HH:MM:SS."""
    h = segundos // 3600
    m = (segundos % 3600) // 60
    s = segundos % 60
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def _campos_ts_de_clip(i: int, clip: Dict) -> Optional[tuple]:
    """Timestamps (inicio_seg, fin_seg) del clip. None si faltan o no parsean."""
    if "inicio" not in clip or "fin" not in clip:
        print(f"      DEBUG clip {i+1}: sin inicio/fin")
        return None

    inicio = str(clip["inicio"])
    fin = str(clip["fin"])

    try:
        return _convertir_ts_simple(inicio), _convertir_ts_simple(fin)
    except Exception as e:
        print(f"      DEBUG clip {i+1}: error parseo ts: {e}")
        return None


def _duracion_valida(i: int, inicio_seg: int, fin_seg: int) -> bool:
    """True si la duración del clip está en el rango aceptado."""
    duracion = fin_seg - inicio_seg
    if duracion < 30 or duracion > 90:
        print(f"      DEBUG clip {i+1}: duracion {duracion}s fuera de rango (15-120)")
        return False
    return True


def _clip_valido(i: int, clip: Dict) -> Optional[Dict]:
    """Normaliza un clip de IA a formato final. None si no pasa la validación."""
    segs = _campos_ts_de_clip(i, clip)
    if segs is None:
        return None
    inicio_seg, fin_seg = segs

    if not _duracion_valida(i, inicio_seg, fin_seg):
        return None

    duracion = fin_seg - inicio_seg
    score = clip.get("score", 5)

    if score < 5:
        print(f"      DEBUG clip {i+1}: score {score} < 5 (umbral mínimo)")
        return None

    criterio = clip.get("criterio_principal", "otro")
    titulo = clip.get("titulo_sugerido", "")

    print(f"      Clip {i+1}: {_formatear_ts_hhmmss(inicio_seg)} - {_formatear_ts_hhmmss(fin_seg)} ({duracion}s) | {criterio} | Score: {score} | {titulo[:40]}")
    return {
        "inicio": _formatear_ts_hhmmss(inicio_seg),
        "fin": _formatear_ts_hhmmss(fin_seg),
        "duracion": duracion,
        "score": score,
        "intensidad": clip.get("intensidad", 5),
        "audio_score": clip.get("audio_score", 5),
        "criterio_principal": criterio,
        "titulo_sugerido": titulo,
        "hook_texto": clip.get("hook_texto", ""),
        "primer_segundo": clip.get("primer_segundo", ""),
        "motivo": clip.get("motivo", ""),
        "tipo_contenido": clip.get("tipo_contenido", "otro"),
    }


def validar_clips(clips: List[Dict]) -> List[Dict]:
    """Valida y filtra los clips."""
    print("[5/6] Validando clips...")

    clips_validos = []

    print(f"      DEBUG: {len(clips)} clips recibidos de IA")

    for i, clip in enumerate(clips):
        valido = _clip_valido(i, clip)
        if valido is not None:
            clips_validos.append(valido)

    clips_validos.sort(key=lambda x: x["score"], reverse=True)
    clips_validos = clips_validos[:10]

    print(f"      Clips válidos: {len(clips_validos)}")
    return clips_validos


def crear_carpeta_salida(nombre: str = "clips") -> str:
    """Crea la carpeta de salida."""
    if not os.path.exists(nombre):
        os.makedirs(nombre)
    return nombre


def _validar_entrada_corte(video_entrada: str, inicio: str, fin: str) -> Optional[int]:
    """Duración del corte en segundos. None si la entrada o el rango son inválidos."""
    # Verificar que el archivo de entrada existe
    if not os.path.exists(video_entrada):
        print(f"      ERROR CRITICO: El archivo de video de entrada NO existe: {video_entrada}")
        return None

    inicio_seg = timestamp_a_segundos(inicio)
    fin_seg = timestamp_a_segundos(fin)
    duracion = int(fin_seg - inicio_seg)

    if duracion <= 0:
        print(f"      Duración inválida: {duracion}s (inicio={inicio}, fin={fin})")
        return None

    print(f"      Corte: {inicio} -> {fin} (duración: {duracion}s)")
    return duracion


def _run_corte_ffmpeg(comando: list) -> bool:
    """Ejecuta el comando de corte y reporta el resultado por consola."""
    try:
        result = subprocess.run(comando, capture_output=True, timeout=120)
        if result.returncode != 0:
            stderr_msg = result.stderr.decode("utf-8", errors="ignore")
            print(f"      Ffmpeg FALLÓ. Return code: {result.returncode}")
            print(f"      Ffmpeg stderr completo:\n{stderr_msg}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"      Timeout al cortar clip")
        return False
    except subprocess.CalledProcessError as e:
        print(f"      Error al cortar: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else e}")
        return False


def cortar_clip(video_entrada: str, inicio: str, fin: str, salida: str) -> bool:
    """Corta un clip usando FFmpeg."""
    # Debug: mostrar qué FFmpeg estamos usando
    ffmpeg_path = shutil.which("ffmpeg")
    print(f"      [DEBUG] Usando FFmpeg en: {ffmpeg_path}")

    duracion = _validar_entrada_corte(video_entrada, inicio, fin)
    if duracion is None:
        return False

    comando = [
        "/usr/local/bin/ffmpeg", "-y",
        "-i", video_entrada,           # Entrada primero
        "-ss", str(inicio),             # Slow seek (después de -i)
        "-t", str(duracion),            # Duración
        "-c:v", "libx264",              # Codec de video estándar
        "-c:a", "aac",                  # Codec de audio estándar
        "-movflags", "+faststart",      # Optimización para web
        salida
    ]
    comando_str = " ".join(comando)
    print(f"      Ejecutando: {comando_str}")

    return _run_corte_ffmpeg(comando)


def procesar_clips(video_entrada: str, clips: List[Dict], carpeta: str) -> List[str]:
    """Genera todos los clips."""
    print("[6/6] Generando clips...")
    
    archivos = []
    info_clips = []
    
    for i, clip in enumerate(clips, 1):
        nombre = os.path.join(carpeta, f"clip_{i}.mp4")
        inicio = str(clip["inicio"])
        fin = str(clip["fin"])
        print(f"      Clip {i}: inicio={inicio}, fin={fin}")
        
        if cortar_clip(video_entrada, inicio, fin, nombre):
            if os.path.exists(nombre):
                tamano = os.path.getsize(nombre)
                print(f"      ✓ Guardado: {nombre} ({tamano} bytes)")
            else:
                print(f"      ✗ Archivo no creado")
            archivos.append(nombre)
            info_clips.append({
                "archivo": nombre,
                "inicio": clip["inicio"],
                "fin": clip["fin"],
                "titulo_sugerido": clip.get("titulo_sugerido", ""),
                "hook_texto": clip.get("hook_texto", ""),
                "criterio_principal": clip.get("criterio_principal", ""),
                "score": clip.get("score", 0),
                "primer_segundo": clip.get("primer_segundo", ""),
                "motivo": clip.get("motivo", ""),
            })
        else:
            print(f"      ✗ Falló")
    
    with open(os.path.join(carpeta, "clips_info.json"), "w", encoding="utf-8") as f:
        json.dump(info_clips, f, indent=2, ensure_ascii=False)
    
    return archivos


def _mostrar_uso() -> None:
    """Imprime el uso del CLI y termina con código 1."""
    print("\nUso:")
    print("  Con transcripción manual: python main.py video.mp4 transcripcion.txt")
    print("  Modo automático (Whisper): python main.py video.mp4")
    print("  Solo mejor clip: python main.py video.mp4 --single")
    print("  Corte manual: python main.py video.mp4 00:01:00 00:01:30")
    print("\nEjemplos:")
    print("  python main.py video.mp4 transcripcion.txt")
    print("  python main.py video.mp4  (usa Whisper automático)")
    print("  python main.py video.mp4 --single")
    print("=" * 50)
    sys.exit(1)


def _validar_args_cli(video: str) -> None:
    """Valida que el video exista y FFmpeg esté disponible; aborta si no."""
    if not os.path.exists(video):
        print(f"\nError: Video '{video}' no encontrado\n")
        sys.exit(1)

    if not verificar_ffmpeg():
        print("\nError: FFmpeg no instalado\n")
        sys.exit(1)


def _corte_manual(video: str, carpeta: str, inicio: str, fin: str) -> None:
    """Ejecuta un corte manual único y termina el programa."""
    print(f"MODO MANUAL: {inicio} -> {fin}")
    print("=" * 50)

    nombre = os.path.join(carpeta, "clip_single.mp4")
    if cortar_clip(video, inicio, fin, nombre):
        if os.path.exists(nombre):
            tamano = os.path.getsize(nombre)
            info_clips = [{"archivo": nombre, "inicio": inicio, "fin": fin}]
            with open(os.path.join(carpeta, "clips_info.json"), "w", encoding="utf-8") as f:
                json.dump(info_clips, f, indent=2)
            print(f"\n✓ Clip guardado: {nombre} ({tamano} bytes)")
            print(f"  Editar con: python editor_viral.py {nombre} clips_editados")
        else:
            print("\n✗ Error: archivo no creado")
    else:
        print("\n✗ Error al cortar clip")
    sys.exit(0)


def _modo_transcripcion_arg() -> tuple:
    """Resuelve el modo cuando se pasa solo video + transcripción/--single."""
    transcripcion_path = sys.argv[2]
    if transcripcion_path == "--single":
        return False, None, True
    if not os.path.exists(transcripcion_path):
        print(f"\nError: Transcripción '{transcripcion_path}' no encontrada\n")
        sys.exit(1)
    return False, transcripcion_path, False


def _modo_desde_args(video: str, carpeta: str) -> tuple:
    """Resuelve (modo_whisper, transcripcion_path, modo_single) según sys.argv."""
    if len(sys.argv) >= 4:
        if sys.argv[3] == "--single":
            return False, sys.argv[2], True
        _corte_manual(video, carpeta, sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 3:
        return _modo_transcripcion_arg()
    return True, None, False


def _datos_audio_de(audio_path: str) -> List[Dict]:
    """Analiza el audio si el módulo está disponible; [] si no."""
    if AUDIO_ANALYZER_AVAILABLE:
        return analizar_audio_video(audio_path)
    print("      Saltando análisis de audio (audio_analyzer no instalado)")
    return []


def _transcripcion_manual_para_ia(transcripcion_path: str) -> str:
    """Parsea la transcripción provista y la prepara para la IA."""
    from whisper_transcriber import parsear_transcripcion_youtube
    print("\n[3/6] Parseando transcripción...")
    parsear_transcripcion_youtube(
        transcripcion_path,
        "transcripcion_formatted.txt"
    )
    texto_para_ia = leer_transcripcion_para_ia("transcripcion_formatted.txt")
    print("      Modo: transcripción manual (instantáneo)")
    return texto_para_ia


def _transcripcion_whisper_para_ia(video: str) -> str:
    """Transcribe el video con faster-whisper y prepara el texto para la IA."""
    from whisper_transcriber import transcribir_video
    print("\n[3/6] Transcribiendo con faster-whisper...")
    print("      Modelo: large-v3-turbo (4x más rápido)")
    transcribir_video(
        video,
        "transcripcion_formatted.txt"
    )
    texto_para_ia = leer_transcripcion_para_ia("transcripcion_formatted.txt")
    print("      Modo: faster-whisper automático")
    return texto_para_ia


def _pedir_transcripcion(video: str, transcripcion_path: Optional[str]) -> str:
    """Usa la transcripción provista si existe; Whisper como fallback."""
    if transcripcion_path and os.path.exists(transcripcion_path):
        return _transcripcion_manual_para_ia(transcripcion_path)
    return _transcripcion_whisper_para_ia(video)


def _obtener_clips_ia_segun_texto(texto_para_ia: str, datos_audio: List[Dict]) -> List[Dict]:
    """Consulta a la IA solo si hay texto de transcripción; [] si no."""
    if not texto_para_ia:
        return []
    datos_enriquecidos = enriquecer_datos_para_ia(datos_audio, "transcripcion_formatted.txt")
    texto_para_ia = preparar_transcripcion_para_ia("transcripcion_formatted.txt")
    return obtener_clips_ia(texto_para_ia, datos_audio, datos_enriquecidos)


def _generar_archivos_finales(video: str, clips_validos: List[Dict], carpeta: str, modo_single: bool) -> List[str]:
    """Procesa todos los clips, o solo el mejor si el modo single está activo."""
    if modo_single:
        print(f"\nProcesando solo el mejor clip (score: {clips_validos[0]['score']})")
        mejor_clip = [clips_validos[0]]
        return procesar_clips(video, mejor_clip, carpeta)
    return procesar_clips(video, clips_validos, carpeta)


def _ejecutar_pipeline_cli(video: str, carpeta: str, modo_whisper: bool, transcripcion_path: Optional[str], modo_single: bool) -> None:
    """Pipeline automático completo del CLI: audio → análisis → transcripción → IA → corte."""
    print("MODO AUTOMÁTICO")
    if modo_single:
        print("  (Solo el mejor clip)")
    if modo_whisper:
        print("  (Transcripción con Whisper)")
    print("=" * 50)

    audio_path = extraer_audio(video)

    datos_audio = _datos_audio_de(audio_path)

    texto_para_ia = _pedir_transcripcion(video, transcripcion_path)

    clips_ia = _obtener_clips_ia_segun_texto(texto_para_ia, datos_audio)

    clips_validos = validar_clips(clips_ia)

    if not clips_validos:
        print("\nNo se encontraron clips válidos")
        sys.exit(0)

    archivos = _generar_archivos_finales(video, clips_validos, carpeta, modo_single)

    print("\n" + "=" * 50)
    print(f"  CLIPS GENERADOS: {len(archivos)}")
    print(f"  UBICACIÓN: {os.path.abspath(carpeta)}")
    print("=" * 50)


def _mensaje_error_principal(e: Exception) -> str:
    """Mensaje de error del CLI según el tipo de excepción."""
    if isinstance(e, ValueError):
        return f"\nError de datos: {e}\n"
    if isinstance(e, ConnectionError):
        return f"\nError de conexión: {e}\n"
    if isinstance(e, TimeoutError):
        return f"\nError de tiempo: {e}\n"
    return f"\nError: {e}\n"


def main():
    """Función principal."""
    print("=" * 50)
    print("  CLIP GENERATOR")
    print("=" * 50)

    if len(sys.argv) < 2:
        _mostrar_uso()

    video = sys.argv[1]

    _validar_args_cli(video)

    carpeta = crear_carpeta_salida("clips")
    print(f"\nCarpeta: {os.path.abspath(carpeta)}\n")

    modo_whisper, transcripcion_path, modo_single = _modo_desde_args(video, carpeta)

    try:
        _ejecutar_pipeline_cli(video, carpeta, modo_whisper, transcripcion_path, modo_single)
    except Exception as e:
        print(_mensaje_error_principal(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
