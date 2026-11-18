from __future__ import annotations

import subprocess
from pathlib import Path

from backend.core.schemas import RenderConfig, TranscriptData, ViralClipCandidate
from backend.services.video_editor.captions import write_ass


SAMPLE_FALLBACK = Path("tests/fixtures/sample.mp4")


def _resolve_sample() -> Path:
    candidates = [
        SAMPLE_FALLBACK,
        Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "sample.mp4",
        Path(__file__).resolve().parents[3] / "backend" / "tests" / "fixtures" / "sample.mp4",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def _generate_ass(transcript: TranscriptData, config: RenderConfig, out: Path) -> Path:
    ass_path = out.with_suffix(".ass")
    write_ass(transcript, str(ass_path), style=config.caption_style)
    if not ass_path.exists():
        raise RuntimeError(f"No se pudo generar ASS en {ass_path}")
    return ass_path


def _auto_crop_filter() -> str:
    return "crop=ih*9/16:ih:(in_w-ih*9/16)/2:0,scale=1080:1920:flags=lanczos"


def _ruta_valida(path: str | None) -> bool:
    """True si el path viene informado y existe."""
    return bool(path) and Path(path).exists()


def _filtro_marca(watermark: str | None, outro: str | None) -> str | None:
    """Filtergraph de overlay de marca. None si no hay marca aplicable."""
    parts: list[str] = []
    if _ruta_valida(watermark):
        parts.append(f"movie={watermark}[wm];[in][wm]overlay=W-w-24:H-h-24:shortest=1")
    if _ruta_valida(outro):
        parts.append(f"movie={outro}[out]")
    if not parts:
        return None
    return ",".join(parts)


def _brand_filter(watermark: str | None, outro: str | None) -> str:
    filtro = _filtro_marca(watermark, outro)
    if filtro is None:
        return ""
    return filtro


def _fuente_video(video_path: str | None) -> Path:
    """Video de entrada o sample de fallback si el path no existe."""
    if video_path and Path(video_path).exists():
        return Path(video_path)
    return _resolve_sample()


def _validar_candidate(candidate: ViralClipCandidate) -> float:
    """Valida la ventana del candidate y devuelve su duración."""
    if candidate.end_time <= candidate.start_time:
        raise ValueError(f"candidate end_time ({candidate.end_time}) debe ser > start_time ({candidate.start_time})")
    duration = candidate.end_time - candidate.start_time
    if duration < 5 or duration > 90:
        raise ValueError(f"Duración {duration}s fuera de rango 5-90s")
    return duration


def _agregar_subs(vf_parts: list[str], transcript: TranscriptData | None, config: RenderConfig, out_path: Path) -> None:
    """Agrega el filtro de subtítulos ASS si hay transcript con words."""
    if transcript and transcript.words:
        ass_path = _generate_ass(transcript, config, out_path)
        vf_parts.append(f"ass={ass_path.as_posix()}")


def _agregar_brand(vf_parts: list[str], config: RenderConfig) -> None:
    """Agrega el filtergraph de marca (watermark/outro) si aplica."""
    brand = _brand_filter(config.watermark_path, config.outro_path)
    if brand:
        vf_parts.append(brand)


def _vf_parts_de(transcript: TranscriptData | None, config: RenderConfig, out_path: Path) -> list[str]:
    """Filtros de video según config y transcript."""
    vf_parts: list[str] = []
    if config.enable_auto_crop:
        vf_parts.append(_auto_crop_filter())

    _agregar_subs(vf_parts, transcript, config, out_path)

    _agregar_brand(vf_parts, config)
    return vf_parts


def _vf_final(vf_parts: list[str]) -> str:
    """Filtergraph final; scale por defecto si queda vacío."""
    return ",".join([p for p in vf_parts if p]) or "scale=1080:1920"


def _ejecutar_render(cmd: list, vf: str, clip_id: str) -> None:
    """Corre ffmpeg para el render y traduce los errores a RuntimeError."""
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    except FileNotFoundError as e:
        raise RuntimeError(f"FFmpeg no instalado o no en PATH: {e}") from e
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore")[:800] if e.stderr else str(e)
        raise RuntimeError(f"FFmpeg render falló (vf={vf}): {err}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"FFmpeg timeout 120s para {clip_id}") from e


async def render_clip(
    video_path: str | None,
    candidate: ViralClipCandidate,
    config: RenderConfig,
    transcript: TranscriptData | None = None,
    output_dir: str = "storage/renders",
) -> str:
    src = _fuente_video(video_path)
    if not src.exists():
        raise FileNotFoundError(f"Video source not found and fallback missing: {src}")

    duration = _validar_candidate(candidate)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{candidate.clip_id}.mp4"

    vf = _vf_final(_vf_parts_de(transcript, config, out_path))

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(candidate.start_time),
        "-i",
        str(src),
        "-t",
        str(duration),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]

    _ejecutar_render(cmd, vf, candidate.clip_id)

    if not out_path.exists():
        raise RuntimeError(f"Render no produjo archivo: {out_path}")

    return str(out_path)


async def render_clip_legacy(
    video_path: str, candidate: ViralClipCandidate, config: RenderConfig
) -> str:
    return await render_clip(video_path, candidate, config)
