"""
import shutil
import platform
Step04_cutwav_mono_crossplatform.py

Purpose (MONO pipeline)
- Cut wav segments based on turn-level timestamps in __result.txt files (SpeakerA/SpeakerB).
- Uses SoX (command: sox) to trim segments from the corresponding split wav file.
- Cross-platform path handling via pathlib.
- Preserves content (no speaker deletion); output wav filenames include speaker + time range.

Input (default):
  output_mono/output_txt_1   (if exists & non-empty) else output_mono/output_txt
  output_mono/split          (the split wav files)
Output:
  output_mono/output_cutwav  (trimmed wav segments)

Environment:
  AUDIOMATIC_ROOT (optional): project root

Notes:
- Requires 'sox' in PATH. Install via conda-forge: conda install -c conda-forge sox=14.4.2
"""

import os
import sys
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
import platform
import shutil


def create_name_match_dict(folder_path: Path) -> dict:
    """Map sanitized filename stem -> actual filename in folder."""
    name_match = {}
    if not folder_path.exists():
        print(f"Error: The folder {folder_path} does not exist.")
        return name_match
    for p in folder_path.iterdir():
        if p.is_file():
            stem_fix = re.sub(r'[^a-zA-Z0-9]', '', p.stem)
            name_match[stem_fix] = p.name
    return name_match


def file_lookup(filename: str, name_match: dict) -> str | None:
    stem = Path(filename).stem
    stem_fix = re.sub(r'[^a-zA-Z0-9]', '', stem)
    return name_match.get(stem_fix)


def convert_time_format(time_str: str) -> str:
    # Convert "00:00:000" to "00m00.000s" (used only for filenames)
    minutes, seconds, milliseconds = re.split('[:.]', time_str)
    return f"{minutes}m{seconds.zfill(2)}.{milliseconds.zfill(3)}s"


def convert_time_format_2(time_str: str) -> str:
    # Convert "00:00:000" to seconds.mmm (used for sox trim)
    minutes, seconds, milliseconds = re.split('[:.]', time_str)
    total_seconds = int(minutes) * 60 + int(seconds)
    return f"{total_seconds}.{milliseconds.zfill(3)}"


def pick_txt_dir(output_mono_dir: Path) -> Path:
    """Prefer output_txt_1 if it exists and is non-empty; else output_txt."""
    cand1 = output_mono_dir / "output_txt_1"
    if cand1.exists() and any(cand1.iterdir()):
        return cand1
    cand2 = output_mono_dir / "output_txt"
    return cand2


def main():
    start_time = time.time()
    start_datetime = datetime.fromtimestamp(start_time)

    # base_dir = Path(os.environ.get("AUDIOMATIC_ROOT", Path(__file__).resolve().parent)).resolve()
    base_dir = Path(os.environ.get("AUDIOMATIC_ROOT") or Path.cwd()).resolve()


    # Resolve SoX binary (Windows: tools/sox.exe; Linux: tools/sox or system sox)
    if platform.system() == "Windows":
        SOX_BIN = str(base_dir / "tools" / "sox.exe")
    else:
        bundled = base_dir / "tools" / "sox"
        if bundled.exists():
            SOX_BIN = str(bundled)
        else:
            SOX_BIN = shutil.which("sox") or "sox"

    output_mono_dir = base_dir / "output_mono"
    output_mono_dir.mkdir(parents=True, exist_ok=True)

    directory_path = pick_txt_dir(output_mono_dir)

    # Check input directory
    if (not directory_path.exists()) or (not any(directory_path.iterdir())):
        print(f"Error: The directory '{directory_path}' is empty or does not exist. Please ensure it contains files before proceeding.")
        sys.exit(1)

    wav_split_path = output_mono_dir / "split"
    if (not wav_split_path.exists()) or (not any(p.suffix.lower()=='.wav' for p in wav_split_path.iterdir())):
        print(f"Error: The directory '{wav_split_path}' is empty or does not exist. Please ensure it contains .wav files.")
        sys.exit(1)

    result_path = output_mono_dir / "output_cutwav"
    result_path.mkdir(parents=True, exist_ok=True)

    name_match = create_name_match_dict(wav_split_path)  # Run only once

    last_result = None
    sox_runs = 0
    sox_failures = 0

    # Parse each __result.txt file
    for txt_file in sorted(directory_path.iterdir()):
        if not (txt_file.is_file() and txt_file.name.endswith("__result.txt")):
            continue

        document_name = txt_file.name[:-len("__result.txt")]  # without suffix
        # The source wav is usually document_name.wav in split folder
        # We use lookup to tolerate different punctuation.
        source_wav_name = file_lookup(f"{document_name}.wav", name_match)

        if not source_wav_name:
            print(f"[WARN] Could not find source wav for {txt_file.name} (expected like {document_name}.wav). Skipping.")
            continue

        with txt_file.open('r', errors='ignore') as f:
            lines = f.readlines()

        line_number = 0
        for line in lines:
            line = line.strip()
            m = re.match(r'(\w+): \[(\d+:\d+:\d+)\] (.+?) \[(\d+:\d+:\d+)\]$', line)
            if not m:
                continue

            line_number += 1
            speaker = m.group(1)  # SpeakerA / SpeakerB
            t_start_raw = m.group(2)
            t_end_raw = m.group(4)

            # For filenames
            t_start_name = convert_time_format(t_start_raw)
            t_end_name = convert_time_format(t_end_raw)

            # For sox trim
            t_start = convert_time_format_2(t_start_raw)
            t_end = convert_time_format_2(t_end_raw)

            formatted_numbers = str(line_number).zfill(3)
            item = f"__{formatted_numbers}_{speaker}_{t_start_name}_to_{t_end_name}"
            out_stem = f"{document_name}{item}"

            in_wav = wav_split_path / source_wav_name
            out_wav = result_path / f"{out_stem}.wav"

            # Run sox
            cmd = [SOX_BIN, str(in_wav), str(out_wav), "trim", str(t_start), f"={t_end}"]
            last_result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            sox_runs += 1
            if last_result.returncode != 0:
                sox_failures += 1
                print(f"[WARN] sox failed (code={last_result.returncode}) for: {' '.join(cmd)}\n{(last_result.stderr or '')[:300]}")

    # Summary
    if sox_runs == 0:
        print("[WARN] No sox commands were executed.")
    else:
        print(f"[INFO] sox runs: {sox_runs}, failures: {sox_failures}")

    end_time = time.time()
    end_datetime = datetime.fromtimestamp(end_time)
    elapsed = end_datetime - start_datetime
    print(f"Step04_cutwav total running time: {elapsed} seconds")


if __name__ == "__main__":
    main()