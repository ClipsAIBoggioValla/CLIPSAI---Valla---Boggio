#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _resolve_video(p: str | None) -> Path:
    cands: list[Path] = []
    if p:
        cands.append(Path(p))
    cands.extend([ROOT / "river.mp4", ROOT / "backend" / "tests" / "fixtures" / "sample.mp4", ROOT / "tests" / "fixtures" / "sample.mp4"])
    for c in cands:
        if c.is_file():
            return c.resolve()
    raise FileNotFoundError(f"Video no encontrado. Probados: {cands}")


def _resolver_o_salir(p: str | None) -> Path:
    """Video resuelto; termina el proceso con código 1 si no hay ninguno."""
    try:
        return _resolve_video(p)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr); sys.exit(1)


def _verificar_ffmpeg_o_salir() -> None:
    """Confirma que FFmpeg esté disponible; termina con código 1 si no."""
    try:
        import subprocess; subprocess.run(["ffmpeg","-version"], capture_output=True, check=True, timeout=5)
        print("[1/3] FFmpeg OK")
    except Exception as exc:
        print(f"[error] FFmpeg no disponible: {exc}", file=sys.stderr); sys.exit(1)


def _hay_archivo_transcript(transcript: str | None) -> bool:
    """True si se pasó un transcript que existe como archivo."""
    return bool(transcript) and Path(transcript).is_file()


def _ts_segundos_hooks(ts: str) -> float | None:
    """'H:MM:SS', 'M:SS' o segundos a float. None si no parsea."""
    try:
        if ":" in ts:
            parts=ts.split(":")
            return int(parts[0])*3600+int(parts[1])*60+float(parts[2]) if len(parts)==3 else int(parts[0])*60+float(parts[1])
        return float(ts)
    except Exception:
        return None


def _segmento_de_linea_hooks(line: str) -> dict | None:
    """Segmento de una línea 'ts - texto' (o línea suelta). None si no aplica."""
    line=line.strip()
    if not line:
        return None
    if " - " not in line:
        return {"start":0,"end":3,"text":line}
    ts, txt = line.split(" - ", 1)
    sec = _ts_segundos_hooks(ts)
    if sec is None:
        return None
    return {"start":sec,"end":sec+3,"text":txt}


def _segmentos_de_archivo(transcript: str) -> list[dict] | None:
    """Segmentos parseados del archivo de transcript. None si quedó vacío."""
    text = Path(transcript).read_text(encoding="utf-8")
    segs: list[dict] = []
    for line in text.splitlines():
        seg = _segmento_de_linea_hooks(line)
        if seg is not None:
            segs.append(seg)
    if segs:
        print(f"[test] transcript file -> {len(segs)} segmentos")
        return segs
    return None


def _segmentos_de_whisper(video: Path) -> list[dict]:
    """Segmentos de Whisper; [] si falla (con traceback en consola)."""
    try:
        from backend_fastapi.app.services.whisper_service import transcribe_video
        print(f"[test] transcribiendo {video} con Whisper...")
        segs = transcribe_video(str(video))
        print(f"[test] Whisper -> {len(segs)} segmentos")
        return [{"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"])} for s in segs]
    except Exception as exc:
        print(f"[test] Whisper fallo: {exc}, usando mock")
        import traceback; traceback.print_exc()
        return []


def _load_segments(video: Path, transcript: str | None, use_mock: bool) -> list[dict]:
    if _hay_archivo_transcript(transcript):
        segs = _segmentos_de_archivo(transcript)
        if segs is not None:
            return segs
    if use_mock:
        return []
    return _segmentos_de_whisper(video)


def _con_mock_fallback(video: Path, segments: list[dict]) -> list[dict]:
    """Reemplaza los segmentos por mocks si no hay ninguno."""
    if not segments:
        from scripts.test_subtitles import _mock_segments  # type: ignore

        raw = _mock_segments(duration=60)
        segments = [{"start": float(s["start"]), "end": float(s["end"]), "text": s["text"]} for s in raw]
        print(f"[test] mock -> {len(segments)} segmentos")
    return segments


def _duracion_probe(probe) -> float | None:
    """Duración del video vía ffprobe. None si el probe falló."""
    return float(probe.stdout.strip()) if probe.returncode==0 and probe.stdout.strip() else None


def _clips_detectados(segments: list[dict], video: Path, args) -> list[dict]:
    """Invoca el detector de hooks; termina con código 1 si el LLM falla."""
    try:
        from backend_fastapi.app.services.hook_service import detect_hooks
        import subprocess
        probe = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", str(video)], capture_output=True, text=True, timeout=10)
        dur = _duracion_probe(probe)
        clips = detect_hooks(segments, duration_hint=dur, mock=args.mock)
    except Exception as exc:
        print(f"[error] LLM fallo: {exc}", file=sys.stderr)
        import traceback; traceback.print_exc(); sys.exit(1)
    return clips


def _salir_si_sin_clips(clips: list[dict]) -> None:
    """Termina con código 0 si el detector no devolvió clips."""
    if not clips:
        print("[result] LLM devolvio 0 clips")
        sys.exit(0)


def _imprimir_clip(i: int, c: dict) -> None:
    """Detalle de un clip detectado por consola."""
    hk = c["hook"]
    print(f" #{i} {c['title']}")
    print(f"    Score: {c['viral_score']} | {c['reasoning']}")
    print(f"    Clip:  {c['start_time']:.1f} -> {c['end_time']:.1f} ({c['end_time']-c['start_time']:.1f}s)")
    print(f"    Hook:  \"{hk['text']}\" ({hk['duration']:.1f}s)")
    print(f"           {hk['start_time']:.1f} -> {hk['end_time']:.1f} (dentro del clip: {c['start_time']<=hk['start_time'] and hk['end_time']<=c['end_time']})")
    print(f"    Final: Hook {hk['duration']:.1f}s + Clip {c['end_time']-c['start_time']:.1f}s = {hk['duration']+c['end_time']-c['start_time']:.1f}s total")
    print()


def _imprimir_clips(clips: list[dict]) -> None:
    """Lista formateada de todos los clips detectados."""
    for i, c in enumerate(clips, 1):
        _imprimir_clip(i, c)


def _limpiar_tmp(keep: bool, tmp_ass_name: str, hooked_video: Path) -> None:
    """Borra los temporales del render o los conserva con su ruta impresa."""
    if not keep:
        for p in [tmp_ass_name, str(hooked_video)]:
            try: Path(p).unlink(missing_ok=True)
            except Exception: pass
    else:
        print(f"      KEEP ASS: {tmp_ass_name}")
        print(f"      KEEP hook video: {hooked_video}")


def _render_primer_clip(video: Path, segments: list[dict], clips: list[dict], keep: bool) -> None:
    """Renderiza el primer hook+clip con ASS desplazado y subtítulos quemados."""
    print("[3/3] Renderizando primer hook+clip con ASS shift...")
    from backend_fastapi.app.services.ass_generator import generate_hooked_ass
    from backend_fastapi.app.services.ffmpeg_service import build_hook_clip, burn_subtitles
    import tempfile
    c = clips[0]; hk = c["hook"]
    tmp_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False); tmp_ass.close()
    tmp_out = tempfile.NamedTemporaryFile(suffix="_hook.mp4", delete=False); tmp_out.close()
    hooked_video = Path(tmp_out.name)
    try:
        generate_hooked_ass(segments, c["start_time"], c["end_time"], hk["start_time"], hk["end_time"], tmp_ass.name, title=c["title"])
        print(f"      ASS hook: {tmp_ass.name} ({Path(tmp_ass.name).stat().st_size} bytes)")
        for line in Path(tmp_ass.name).read_text(encoding="utf-8").splitlines()[:8]:
            print(f"        {line}")
        build_hook_clip(video, c["start_time"], c["end_time"], hk["start_time"], hk["end_time"], hooked_video)
        print(f"      Hook video (sin subs): {hooked_video} ({hooked_video.stat().st_size} bytes)")
        # burn subtitles over concatenated video
        final_out = Path(tempfile.gettempdir()) / f"{video.stem}_hooked_subtitled.mp4"
        burn_subtitles(hooked_video, tmp_ass.name, final_out)
        print(f"      [OK] Final hook+clip subtitulado: {final_out} ({final_out.stat().st_size} bytes)")
        print(f"      Duracion hook {hk['duration']:.1f}s desplazada: hook 0->{hk['duration']:.1f}s, clip {hk['duration']:.1f}->{hk['duration']+c['end_time']-c['start_time']:.1f}s")
        if not keep:
            print("      (tmp ASS/video intermedios limpiados)")
    except Exception as exc:
        print(f"[error] render fallo: {exc}", file=sys.stderr)
        import traceback; traceback.print_exc()
    finally:
        _limpiar_tmp(keep, tmp_ass.name, hooked_video)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Hook Teaser 5s + Clip 15-60s (Issue 11)")
    parser.add_argument("video", nargs="?", default=None, help="video mp4 (default river.mp4)")
    parser.add_argument("--transcript", default=None, help="transcripcion txt opcional")
    parser.add_argument("--mock", action="store_true", help="forzar mock sin LLM")
    parser.add_argument("--keep", action="store_true", help="no borrar ASS/mp4 generados")
    parser.add_argument("--render", action="store_true", help="ademas renderizar hook+clip concatenado con subtitles")
    args = parser.parse_args()

    video = _resolver_o_salir(args.video)
    print(f"[1/3] Video: {video} ({video.stat().st_size} bytes)")
    _verificar_ffmpeg_o_salir()

    segments = _load_segments(video, args.transcript, use_mock=args.mock)
    if args.mock:
        segments = _con_mock_fallback(video, segments)
    print(f"[2/3] Invocando LLM hook detector (transcript {len(segments)} segs)...")
    clips = _clips_detectados(segments, video, args)

    _salir_si_sin_clips(clips)

    print(f"\n[result] {len(clips)} clips detectados:\n{'='*60}")
    _imprimir_clips(clips)

    if args.render:
        _render_primer_clip(video, segments, clips, args.keep)

if __name__ == "__main__":
    main()
