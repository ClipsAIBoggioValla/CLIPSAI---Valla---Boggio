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

def _load_segments(video: Path, transcript: str | None, use_mock: bool) -> list[dict]:
    if transcript and Path(transcript).is_file():
        text = Path(transcript).read_text(encoding="utf-8")
        segs: list[dict] = []
        for line in text.splitlines():
            line=line.strip()
            if not line: continue
            if " - " in line:
                ts, txt = line.split(" - ", 1)
                try:
                    if ":" in ts:
                        parts=ts.split(":")
                        sec=int(parts[0])*3600+int(parts[1])*60+float(parts[2]) if len(parts)==3 else int(parts[0])*60+float(parts[1])
                    else:
                        sec=float(ts)
                    segs.append({"start":sec,"end":sec+3,"text":txt})
                except Exception: continue
            else:
                segs.append({"start":0,"end":3,"text":line})
        if segs:
            print(f"[test] transcript file -> {len(segs)} segmentos")
            return segs
    if use_mock:
        return []
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

def main() -> None:
    parser = argparse.ArgumentParser(description="Test Hook Teaser 5s + Clip 15-60s (Issue 11)")
    parser.add_argument("video", nargs="?", default=None, help="video mp4 (default river.mp4)")
    parser.add_argument("--transcript", default=None, help="transcripcion txt opcional")
    parser.add_argument("--mock", action="store_true", help="forzar mock sin LLM")
    parser.add_argument("--keep", action="store_true", help="no borrar ASS/mp4 generados")
    parser.add_argument("--render", action="store_true", help="ademas renderizar hook+clip concatenado con subtitles")
    args = parser.parse_args()

    try:
        video = _resolve_video(args.video)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr); sys.exit(1)
    print(f"[1/3] Video: {video} ({video.stat().st_size} bytes)")
    try:
        import subprocess; subprocess.run(["ffmpeg","-version"], capture_output=True, check=True, timeout=5)
        print("[1/3] FFmpeg OK")
    except Exception as exc:
        print(f"[error] FFmpeg no disponible: {exc}", file=sys.stderr); sys.exit(1)

    segments = _load_segments(video, args.transcript, use_mock=False if not args.mock else True)
    if args.mock or not segments:
        if not segments:
            from scripts.test_subtitles import _mock_segments  # type: ignore

            raw = _mock_segments(duration=60)
            segments = [{"start": float(s["start"]), "end": float(s["end"]), "text": s["text"]} for s in raw]
            print(f"[test] mock -> {len(segments)} segmentos")
    print(f"[2/3] Invocando LLM hook detector (transcript {len(segments)} segs)...")
    try:
        from backend_fastapi.app.services.hook_service import detect_hooks
        import subprocess
        probe = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", str(video)], capture_output=True, text=True, timeout=10)
        dur = float(probe.stdout.strip()) if probe.returncode==0 and probe.stdout.strip() else None
        clips = detect_hooks(segments, duration_hint=dur, mock=args.mock)
    except Exception as exc:
        print(f"[error] LLM fallo: {exc}", file=sys.stderr)
        import traceback; traceback.print_exc(); sys.exit(1)

    if not clips:
        print("[result] LLM devolvio 0 clips")
        sys.exit(0)

    print(f"\n[result] {len(clips)} clips detectados:\n{'='*60}")
    for i, c in enumerate(clips, 1):
        hk = c["hook"]
        print(f" #{i} {c['title']}")
        print(f"    Score: {c['viral_score']} | {c['reasoning']}")
        print(f"    Clip:  {c['start_time']:.1f} -> {c['end_time']:.1f} ({c['end_time']-c['start_time']:.1f}s)")
        print(f"    Hook:  \"{hk['text']}\" ({hk['duration']:.1f}s)")
        print(f"           {hk['start_time']:.1f} -> {hk['end_time']:.1f} (dentro del clip: {c['start_time']<=hk['start_time'] and hk['end_time']<=c['end_time']})")
        print(f"    Final: Hook {hk['duration']:.1f}s + Clip {c['end_time']-c['start_time']:.1f}s = {hk['duration']+c['end_time']-c['start_time']:.1f}s total")
        print()

    if args.render and clips:
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
            if not args.keep:
                print("      (tmp ASS/video intermedios limpiados)")
        except Exception as exc:
            print(f"[error] render fallo: {exc}", file=sys.stderr)
            import traceback; traceback.print_exc()
        finally:
            if not args.keep:
                for p in [tmp_ass.name, str(hooked_video)]:
                    try: Path(p).unlink(missing_ok=True)
                    except Exception: pass
            else:
                print(f"      KEEP ASS: {tmp_ass.name}")
                print(f"      KEEP hook video: {hooked_video}")

if __name__ == "__main__":
    main()
