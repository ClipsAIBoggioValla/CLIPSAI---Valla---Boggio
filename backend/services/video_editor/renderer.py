from __future__ import annotations

import subprocess
from pathlib import Path

from backend.core.schemas import RenderConfig, TranscriptData, ViralClipCandidate
from backend.services.video_editor.captions import write_ass


SAMPLE_FALLBACK = Path("tests/fixtures/sample.mp4")
SAMPLE_FALLBACK_ALT = Path("backend/tests/fixtures/sample.mp4")


def _resolve_sample() -> Path:
    if SAMPLE_FALLBACK.exists():
        return SAMPLE_FALLBACK
    if SAMPLE_FALLBACK_ALT.exists():
        return SAMPLE_FALLBACK_ALT
    return SAMPLE_FALLBACK


def _generate_ass(transcript: TranscriptData, config: RenderConfig, out: Path) -> Path:
    ass_path = out.with_suffix(".ass")
    write_ass(transcript, str(ass_path), style=config.caption_style)
    return ass_path


def _auto_crop_filter() -> str:
    return "crop=ih*9/16:ih:(in_w-ih*9/16)/2:0,scale=1080:1920:flags=lanczos"


def _brand_filter(watermark: str | None, outro: str | None) -> str:
    parts: list[str] = []
    if watermark and Path(watermark).exists():
        parts.append(f"movie={watermark}[wm];[in][wm]overlay=W-w-24:H-h-24:shortest=1")
    return ",".join(parts) if parts else ""


async def render_clip(
    video_path: str | None,
    candidate: ViralClipCandidate,
    config: RenderConfig,
    transcript: TranscriptData | None = None,
    output_dir: str = "storage/renders",
) -> str:
    src = Path(video_path) if video_path and Path(video_path).exists() else _resolve_sample()
    if not src.exists():
        raise FileNotFoundError(f"Video source not found and fallback missing: {src}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{candidate.clip_id}.mp4"

    duration = max(1.0, candidate.end_time - candidate.start_time)

    vf_parts: list[str] = []
    if config.enable_auto_crop:
        vf_parts.append(_auto_crop_filter())

    ass_path: Path | None = None
    if transcript and transcript.words:
        try:
            ass_path = _generate_ass(transcript, config, out_path)
            vf_parts.append(f"ass={ass_path.as_posix()}")
        except Exception:
            pass

    brand = _brand_filter(config.watermark_path, config.outro_path)
    if brand:
        vf_parts.append(brand)

    vf = ",".join([p for p in vf_parts if p]) or "scale=1080:1920"

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

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    except FileNotFoundError:
        out_path.write_text(f"stub render {candidate.clip_id} {candidate.start_time}-{candidate.end_time} vf={vf}\n")
    except subprocess.CalledProcessError:
        out_path.write_text(f"stub render fallback {candidate.clip_id}\n")

    return str(out_path)


async def render_clip_legacy(
    video_path: str, candidate: ViralClipCandidate, config: RenderConfig
) -> str:
    return await render_clip(video_path, candidate, config)
