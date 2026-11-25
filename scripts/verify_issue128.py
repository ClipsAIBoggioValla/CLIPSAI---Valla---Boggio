"""Generate Issue #128 render evidence from local podcast material."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import librosa
import mediapipe as mp
import numpy as np
import cv2

import audio_analyzer as aa
import video_processor as vp

SOURCE = ROOT / "clips" / "clip_1.mp4"
OUT = ROOT / "gaming_procesado" / "clips"
FIXTURE = ROOT / "gaming_procesado" / "tests" / "fixtures" / "issue128_split_fixture.mp4"
FALLBACK_FIXTURE = ROOT / "gaming_procesado" / "tests" / "fixtures" / "issue128_fallback_fixture.mp4"
METRICS = ROOT / "gaming_procesado" / "docs" / "evidencia_128_metricas.md"
MODEL = Path.home() / "AppData" / "Local" / "Temp" / "opencode" / "face_detection_yunet_2023mar.onnx"
MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/refs/heads/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
_YUNET_DETECTOR = None
NAMES = (
    "issue128_single_9_16.mp4",
    "issue128_podcast_split_rms.mp4",
    "issue128_fallback_neutro.mp4",
)


def _ensure_model() -> None:
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    if not MODEL.exists():
        urllib.request.urlretrieve(MODEL_URL, MODEL)


class _LegacyFaceDetection:
    def __init__(self, **options):
        global _YUNET_DETECTOR
        if _YUNET_DETECTOR is None:
            _YUNET_DETECTOR = cv2.FaceDetectorYN.create(str(MODEL), "", (320, 360), 0.6, 0.3, 5000)
        self.detector = _YUNET_DETECTOR

    def process(self, rgb: np.ndarray):
        self.detector.setInputSize((rgb.shape[1], rgb.shape[0]))
        _, detections = self.detector.detect(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        boxes = [_legacy_box(box[:4], rgb.shape[1], rgb.shape[0])
                 for box in ([] if detections is None else detections)]
        return SimpleNamespace(detections=boxes)


def _legacy_box(box, width: int, height: int):
    x, y, w, h = map(int, box)
    relative = SimpleNamespace(
        xmin=x / width,
        ymin=y / height,
        width=w / width,
        height=h / height,
    )
    return SimpleNamespace(location_data=SimpleNamespace(relative_bounding_box=relative))


def _install_legacy_adapter() -> None:
    if hasattr(mp, "solutions"):
        return
    mp.solutions = SimpleNamespace(
        face_detection=SimpleNamespace(FaceDetection=_LegacyFaceDetection)
    )


def _relative_ass_path(ass_file: str) -> str | None:
    if not Path(ass_file).exists():
        return None
    relative = os.path.relpath(ass_file, ROOT).replace("\\", "/")
    return f"ass={relative}"


def _install_ffmpeg8_crop_adapter() -> None:
    crop = vp._filtro_crop_tracking

    def compatible_crop(points):
        return crop(points).replace(":eval=frame", "")

    vp._filtro_crop_tracking = compatible_crop


def _utf8_logs() -> None:
    for handler in vp.logger.handlers:
        stream = getattr(handler, "stream", None)
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)


def _load_video_audio(ffmpeg: str, video: Path) -> tuple[np.ndarray, int]:
    with tempfile.TemporaryDirectory(prefix="issue128_audio_") as folder:
        wav = Path(folder) / "audio.wav"
        _run([ffmpeg, "-y", "-i", str(video), "-vn", "-ac", "2", "-ar", "44100",
              "-c:a", "pcm_s16le", str(wav)])
        return librosa.load(str(wav), sr=None, mono=False)


def _make_fixture(ffmpeg: str) -> None:
    command = [ffmpeg, "-y", "-stream_loop", "-1", "-i", str(SOURCE)]
    command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=91"]
    command += ["-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100:duration=91"]
    graph = (
        "[0:v]split=2[a][b];"
        "[a]scale=640:400,pad=640:720:(ow-iw)/2:(oh-ih)/2,setsar=1[l];"
        "[b]hflip,scale=640:400,pad=640:720:(ow-iw)/2:(oh-ih)/2,setsar=1[r];"
        "[l][r]hstack=inputs=2[v];"
        "[1:a]volume='if(lt(t,45),1,0.03)':eval=frame[left];"
        "[2:a]volume='if(lt(t,45),0.03,1)':eval=frame[right];"
        "[left][right]amerge=inputs=2[a]"
    )
    _run(command + ["-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-t", "91",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                    "-g", "30", "-keyint_min", "30", "-sc_threshold", "0",
                    "-c:a", "aac", "-b:a", "96k", str(FIXTURE)])


def _make_fallback_fixture(ffmpeg: str) -> None:
    _run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x202020:s=1280x720:r=30:d=151",
          "-i", str(SOURCE), "-map", "0:v", "-map", "1:a", "-t", "151",
          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
          "-g", "30", "-keyint_min", "30", "-sc_threshold", "0",
          "-c:a", "aac", "-b:a", "96k", str(FALLBACK_FIXTURE)])


def _segments(duration: float) -> list[dict]:
    return [
        {"start": 1.0, "end": min(5.0, duration), "text": "CLIP DE PRUEBA"},
        {"start": min(20.0, duration - 1), "end": min(25.0, duration), "text": "SEGUNDO SEGMENTO"},
    ]


def _render(name: str, source: Path, layout: str, rms: list[dict] | None = None,
            duration: int = 61) -> dict:
    started = time.perf_counter()
    trajectories = vp._trayectorias_layout(str(source), layout)
    detection_seconds = time.perf_counter() - started
    detection = {"seconds": detection_seconds, "faces": [len(points) for points in trajectories]}
    timings = {"render": 0.0}
    original_overhead = vp._log_tracking_overhead

    def measured_overhead(detection_seconds, render_seconds):
        timings["render"] = render_seconds
        return original_overhead(detection_seconds, render_seconds)

    vp._log_tracking_overhead = measured_overhead
    try:
        with tempfile.TemporaryDirectory(prefix="issue128_ass_") as folder:
            ass = str(Path(folder) / "subtitles.ass")
            vp.generate_ass_from_segments(_segments(duration), 0, duration, ass)
            ok = vp.reframe_and_burn_subtitles(
                str(source), str(OUT / name), ass_file=ass,
                trayectoria=trajectories[0], trayectoria_izq=trajectories[1],
                trayectoria_der=trajectories[2], rms_ventanas=rms,
                deteccion_seconds=detection_seconds, layout=layout,
            )
    finally:
        vp._log_tracking_overhead = original_overhead
    if not ok or timings["render"] <= 0:
        raise RuntimeError(f"Render falló: {name}")
    row = _probe(OUT / name, detection, detection_seconds + timings["render"], timings["render"])
    if rms is not None:
        faces = {"left": trajectories[1], "right": trajectories[2]}
        row["active_events"] = aa.cruzar_rostros_rms(faces, rms)
    return row


def _probe(path: Path, detection: dict, total: float, render: float) -> dict:
    command = ["ffprobe", "-v", "error", "-show_entries",
               "format=duration,size:stream=codec_type,width,height,channels",
               "-of", "json", str(path)]
    info = json.loads(subprocess.run(command, check=True, capture_output=True, text=True).stdout)
    fmt = info["format"]
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "duration": float(fmt["duration"]),
        "detection": detection["seconds"],
        "render": render,
        "total": total,
        "overhead": 100 * detection["seconds"] / max(render, 0.001),
        "faces": detection["faces"],
        "streams": info["streams"],
    }


def _write_metrics(rows: list[dict]) -> None:
    lines = [
        "# Evidencia Issue #128 — tracking y Active Speaker",
        "",
        "Fuente: `clips/clip_1.mp4` (podcast River, 576x360, 61 s; L/R duplicados).",
        "Fixture RMS: 91 s, alterna L/R a los 45 s; fixture fallback: 151 s sin rostros.",
        "Detección: OpenCV YuNet mediante adaptador de API legacy (MediaPipe Tasks no carga",
        "su biblioteca C con Python 3.14). Teaser desactivado para aislar #128;",
        "`video_processor.py` y `audio_analyzer.py` no se modificaron.",
        "El split usa RMS sintético alterno; el fallback usa video sin rostros y audio mono duplicado.",
        "",
        "| Clip | duración (s) | tamaño (MiB) | detección (s) | render cuerpo (s) | pipeline (s) | overhead | puntos/eventos |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        faces = ",".join(map(str, row["faces"]))
        active = ",".join(event["panel"] for event in row.get("active_events", [])) or "—"
        lines.append(
            f"| `{row['file']}` | {row['duration']:.2f} | {row['bytes'] / 1048576:.2f} "
            f"| {row['detection']:.3f} | {row['render']:.3f} | {row['total']:.3f} "
            f"| {row['overhead']:.2f}% | {faces} ({active}) |"
        )
    lines += ["", "## ffprobe", ""]
    for row in rows:
        lines.append(f"### `{row['file']}` ({row['bytes']} bytes)")
        lines.append("```json")
        lines.append(json.dumps(row["streams"], indent=2))
        lines.append("```")
    METRICS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg no está en PATH")
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    targets = [OUT / name for name in NAMES]
    OUT.mkdir(parents=True, exist_ok=True)
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    vp.FFMPEG_BIN = ffmpeg
    _utf8_logs()
    _ensure_model()
    _install_legacy_adapter()
    vp._filtro_ass = _relative_ass_path
    _install_ffmpeg8_crop_adapter()
    _make_fixture(ffmpeg)
    _make_fallback_fixture(ffmpeg)
    fixture_audio, sr = _load_video_audio(ffmpeg, FIXTURE)
    rms_split = aa.rms_por_ventana(fixture_audio, sr)
    actual_audio, actual_sr = _load_video_audio(ffmpeg, FALLBACK_FIXTURE)
    rms_fallback = aa.rms_por_ventana(actual_audio, actual_sr)
    rows = [
        _render(NAMES[0], SOURCE, "single_9_16"),
        _render(NAMES[1], FIXTURE, "podcast_split", rms_split, duration=91),
        _render(NAMES[2], FALLBACK_FIXTURE, "podcast_split", rms_fallback, duration=151),
    ]
    _write_metrics(rows)
    print(json.dumps(rows, indent=2))
    print(f"fixture={FIXTURE.relative_to(ROOT)} size={FIXTURE.stat().st_size}")
    print(f"metrics={METRICS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
