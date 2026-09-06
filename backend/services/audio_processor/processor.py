from __future__ import annotations

from backend.core.schemas import AudioFeatures


async def normalize_audio(video_path: str, video_id: str, target_lufs: float = -14.0) -> AudioFeatures:
    try:
        from backend.track_a.audio.analyzer import AudioAnalyzer

        analyzer = AudioAnalyzer()
        return await analyzer.analyze(video_path, video_id)
    except Exception:
        return AudioFeatures(video_id=video_id, duration_seconds=0.0, events=[], viral_moments=[])


async def loudnorm_filter_args(i: float = -14.0, tp: float = -1.5, lra: float = 11.0) -> list[str]:
    return ["-filter:a", f"loudnorm=I={i}:TP={tp}:LRA={lra}"]
