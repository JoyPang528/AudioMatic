"""
Step03_json_to_txt_mono.py (cross-platform)

Purpose
- Convert WhisperX mono JSON (with word-level speaker labels) into a turn-by-turn TXT.
- Preserve ALL content even if diarization occasionally produces >2 speakers.
- Output only two speakers: SpeakerA and SpeakerB.
  - Pick top-2 speakers by total word count across the call.
  - Any other speaker segments are attached to the previous speaker turn (keeps information).

Usage (Linux/Mac):
  export AUDIOMATIC_ROOT=/path/to/AudioMatic_project
  python Step03_json_to_txt_mono.py

Or override folders:
  python Step03_json_to_txt_mono.py --input_dir /path/to/output_mono/output_json --output_dir /path/to/output_mono/output_txt

Windows (PowerShell):
  $env:AUDIOMATIC_ROOT="C:\path\to\AudioMatic_project"
  python Step03_json_to_txt_mono.py
"""

import argparse
import json
import os
from collections import Counter
from pathlib import Path

# -----------------------------
# Time formatting helpers
# -----------------------------
def format_time(time_value: float) -> str:
    minutes = int(time_value // 60)
    seconds = int(time_value % 60)

    # Milliseconds with stable formatting (avoid float repr issues)
    ms = int(round((time_value - int(time_value)) * 1000))
    if ms < 0:
        ms = 0
    if ms > 999:
        ms = 999

    return f"[{minutes:02}:{seconds:02}:{ms:03}]"


# -----------------------------
# Core processing
# -----------------------------
def extract_main_speaker(segment: dict):
    """Choose the most frequent word-level speaker label in this segment."""
    speaker_counts = Counter()
    for w in (segment.get("words") or []):
        spk = w.get("speaker")
        if spk:
            speaker_counts[spk] += 1
    if not speaker_counts:
        return None
    return speaker_counts.most_common(1)[0][0]


def build_segments(data: dict):
    """Convert WhisperX JSON to a list of {speaker, start, end, text} segments."""
    segments = []
    for seg in (data.get("segments") or []):
        spk = extract_main_speaker(seg)
        if not spk:
            continue
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        segments.append({
            "speaker": spk,
            "start": float(seg.get("start", 0.0)),
            "end": float(seg.get("end", 0.0)),
            "text": text,
            "word_count": len(seg.get("words") or []),
        })
    return segments


def merge_consecutive(segments):
    """Merge adjacent segments with the same speaker label."""
    merged = []
    cur = None
    for s in segments:
        if cur and s["speaker"] == cur["speaker"]:
            cur["text"] += " " + s["text"]
            cur["end"] = s["end"]
            cur["word_count"] = cur.get("word_count", 0) + s.get("word_count", 0)
        else:
            if cur:
                merged.append(cur)
            cur = dict(s)
    if cur:
        merged.append(cur)
    return merged


def map_to_two_speakers(merged):
    """Map arbitrary speakers to SpeakerA/SpeakerB, preserving extra-speaker content."""
    totals = Counter()
    for t in merged:
        totals[t["speaker"]] += max(1, t.get("word_count", 0))

    top2 = [spk for spk, _ in totals.most_common(2)]
    if len(top2) == 0:
        return []
    if len(top2) == 1:
        top2.append(top2[0])

    a_raw, b_raw = top2[0], top2[1]

    mapped = []
    last_out_spk = "SpeakerA"
    for t in merged:
        raw = t["speaker"]
        if raw == a_raw:
            out_spk = "SpeakerA"
        elif raw == b_raw:
            out_spk = "SpeakerB"
        else:
            # Preserve content: attach unknown speaker to previous turn speaker
            out_spk = last_out_spk

        mapped.append({
            "speaker": out_spk,
            "start": t["start"],
            "end": t["end"],
            "text": t["text"],
            "word_count": t.get("word_count", 0),
        })
        last_out_spk = out_spk

    # Merge again after mapping
    mapped = merge_consecutive(mapped)
    return mapped


def format_turns(turns):
    lines = []
    for t in turns:
        lines.append(f"{t['speaker']}: {format_time(t['start'])} {t['text']} {format_time(t['end'])}")
    return "\n".join(lines)


def process_json_file(json_path: Path) -> str:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    segs = build_segments(data)
    merged = merge_consecutive(segs)
    mapped = map_to_two_speakers(merged)
    return format_turns(mapped)


def process_directory(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json"])
    if not json_files:
        print(f"[WARN] No JSON files found in: {input_dir}")
        return

    for jp in json_files:
        print(f"Processing: {jp.name}")
        out_txt = process_json_file(jp)
        out_path = output_dir / f"{jp.stem}__result.txt"
        out_path.write_text(out_txt, encoding="utf-8")
        print(f"Saved: {out_path}")


def main():
    # BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT", Path(__file__).resolve().parent)).resolve()
    BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT") or Path.cwd()).resolve()


    default_input = BASE_DIR / "output_mono" / "output_json"
    default_output = BASE_DIR / "output_mono" / "output_txt"

    ap = argparse.ArgumentParser()
    ap.add_argument("--input_dir", type=str, default=str(default_input))
    ap.add_argument("--output_dir", type=str, default=str(default_output))
    args = ap.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    process_directory(input_dir, output_dir)


if __name__ == "__main__":
    main()
