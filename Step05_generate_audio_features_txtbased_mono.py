import os
import csv
import pandas as pd
import numpy as np
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
import platform
import stat
from typing import List, Union

"""
Step05_audio_mono_crossplatform.py

Input:
  - output_mono/output_txt/*.txt  (from mono Step03)
  - output_mono/output_cutwav/*.wav (from mono Step04)

Output:
  - output_mono/audio_features.csv

Notes:
  - Tries to run external Praat binary first ("praat" or "praat.exe").
    If it fails (e.g., GLIBC mismatch), falls back to parselmouth.praat.run_file.
  - Uses Path everywhere; converts to str only when calling subprocess / parselmouth.
"""

start_time = time.time()
start_datetime = datetime.fromtimestamp(start_time)

# BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT", Path(__file__).resolve().parent)).resolve()
BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT") or Path.cwd()).resolve()

OUTPUT_DIR = BASE_DIR / "output_mono"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Mono TXT from Step03
directory_path = OUTPUT_DIR / "output_txt"

# Praat binary
praat_path = BASE_DIR / ("praat.exe" if platform.system() == "Windows" else "praat")

# Cut wavs from Step04
input_wav_directory = OUTPUT_DIR / "output_cutwav"

# Temporary per-segment CSV output dir
output_wav_directory = OUTPUT_DIR / "output_csv"
output_wav_directory.mkdir(parents=True, exist_ok=True)


def _chmod_x_if_needed(p: Path) -> None:
    """Best-effort chmod +x on Unix if file exists but isn't executable."""
    try:
        if platform.system() != "Windows" and p.exists():
            st = p.stat()
            if not (st.st_mode & stat.S_IXUSR):
                p.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass


def _normalize_rows_width(rows, width, fill_value="/"):
    fixed = []
    for r in rows:
        r = list(r) if not isinstance(r, list) else r
        if len(r) < width:
            r = r + [fill_value] * (width - len(r))
        elif len(r) > width:
            r = r[:width]
        fixed.append(r)
    return np.asarray(fixed, dtype=object)


def run_praat_script_try_bin_then_parselmouth(
    praat_bin: Union[str, Path],
    script_path: Union[str, Path],
    args: List[Union[str, Path]],
    verbose: bool = True,
) -> str:
    """Try external praat --run first; if it fails, fallback to parselmouth.praat.run_file."""
    praat_bin = Path(praat_bin)
    script_path = Path(script_path)

    _chmod_x_if_needed(praat_bin)

    if praat_bin.exists():
        cmd = [str(praat_bin), "--run", str(script_path)] + [str(a) for a in args]
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if p.returncode == 0:
                return "praat_bin"
            if verbose:
                print(f"[WARN] Praat bin failed (code={p.returncode}) for: {' '.join(cmd)}\n{(p.stderr or '')[:300]}")
        except PermissionError as e:
            # Try chmod then retry once
            if verbose:
                print(f"[WARN] Praat permission error: {e}. Trying chmod +x and retry...")
            _chmod_x_if_needed(praat_bin)
            try:
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if p.returncode == 0:
                    return "praat_bin"
                if verbose:
                    print(f"[WARN] Praat bin failed (code={p.returncode}) for: {' '.join(cmd)}\n{(p.stderr or '')[:300]}")
            except Exception as e2:
                if verbose:
                    print(f"[WARN] Praat bin exception after chmod: {e2}")
        except Exception as e:
            if verbose:
                print(f"[WARN] Praat bin exception: {e}")

    # Fallback: Parselmouth (Praat engine in Python; avoids GLIBC mismatch)
    from parselmouth.praat import run_file
    run_file(str(script_path), *[str(a) for a in args])
    return "parselmouth"


def _ensure_csv_exists(csv_path: Path, num_cols: int) -> None:
    """If Praat produced no CSV (e.g., short/empty segments), create a placeholder row."""
    if csv_path.is_file():
        return
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["--undefined--"] * num_cols)


def _read_csv_row_simple(csv_path: Path) -> List[str]:
    txt = csv_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not txt:
        return []
    return txt.split(",")


def _combine_csvs_by_prefix(output_dir: Path, pad_cols_if_missing: int) -> List[List[str]]:
    """Group CSVs by prefix before '__', then combine in pairs (A+B)."""
    csv_files = sorted([p.name for p in output_dir.iterdir() if p.suffix.lower() == ".csv"])
    groups = {}
    for fn in csv_files:
        prefix = fn.split("__")[0]
        groups.setdefault(prefix, []).append(fn)

    combined: List[List[str]] = []
    for prefix, files in groups.items():
        for i in range(0, len(files), 2):
            d1 = _read_csv_row_simple(output_dir / files[i])
            if i + 1 < len(files):
                d2 = _read_csv_row_simple(output_dir / files[i + 1])
                combined.append(d1 + d2)
            else:
                combined.append(d1 + (["/"] * pad_cols_if_missing))
    return combined


def _remove_csvs(output_dir: Path) -> None:
    for p in output_dir.iterdir():
        if p.suffix.lower() == ".csv":
            try:
                p.unlink()
            except Exception:
                pass


def run_stage_for_wavs(
    praat_script_name: str,
    wav_files: List[str],
    input_dir: Path,
    output_dir: Path,
    praat_bin: Path,
    placeholder_cols: int,
    pad_cols_if_missing: int,
    include_zero_arg: bool,
) -> List[List[str]]:
    """Run one Praat stage (S1/S2/S3/S4) for all wavs, then combine outputs once."""
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = BASE_DIR / praat_script_name

    for wav_file in wav_files:
        if not wav_file.lower().endswith(".wav"):
            continue

        wav_path = input_dir / wav_file
        csv_path = output_dir / (Path(wav_file).stem + ".csv")

        args = (["0.0", wav_path, csv_path] if include_zero_arg else [wav_path, csv_path])

        run_praat_script_try_bin_then_parselmouth(
            praat_bin=praat_bin,
            script_path=script_path,
            args=args,
            verbose=True,
        )
        _ensure_csv_exists(csv_path, placeholder_cols)

    combined = _combine_csvs_by_prefix(output_dir, pad_cols_if_missing)
    _remove_csvs(output_dir)
    return combined


# ---- Validate inputs ----
if (not directory_path.exists()) or (not any(directory_path.iterdir())):
    raise FileNotFoundError(f"Mono TXT directory is empty or missing: {directory_path}")

if (not input_wav_directory.exists()) or (not any(p.suffix.lower() == ".wav" for p in input_wav_directory.iterdir())):
    raise FileNotFoundError(f"Mono cutwav directory is empty or missing: {input_wav_directory}")


# ---- Gather __result.txt files ----
result_files = sorted([p for p in directory_path.iterdir() if p.is_file() and p.name.endswith("__result.txt")])
file_dict = {re.sub(r'__result\.txt$', '', p.name): p for p in result_files}


def extract_data_from_line(line: str):
    """
    Parse mono Step03 lines like:
      SpeakerA: [00:00:000] hello there [00:01:234]
    """
    pattern = r'(?P<source>SpeakerA|SpeakerB): \[(?P<start>[\d:]+)\] (?P<text>.+?) \[(?P<end>[\d:]+)\]\s*$'
    m = re.match(pattern, line.strip())
    if not m:
        return None
    return m.groupdict()


def process_txt_file(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        d = extract_data_from_line(line)
        if d:
            rows.append(d)
    return rows


def calculate_speech_rate_words_s(speaker: str, start_time: str, text: str, end_time: str):
    st = start_time.split(":")
    et = end_time.split(":")
    start_seconds = (int(st[0]) * 60) + int(st[1]) + (int(st[2]) / 1000)
    end_seconds = (int(et[0]) * 60) + int(et[1]) + (int(et[2]) / 1000)
    duration = max(0.0, end_seconds - start_seconds)
    words = len(text.split())
    return duration, (words / duration if duration > 0 else 0.0)


def extract_number(filename: str) -> int:
    # matches __001_SpeakerA... or __001_SpeakerB...
    m = re.search(r'__(\d+)(?=_SpeakerA|_SpeakerB)', filename)
    return int(m.group(1)) if m else 10**18


all_results = []

for call_id, txt_path in file_dict.items():
    result_data = process_txt_file(txt_path)

    # Build the 10-column "text+timing" block (same schema as stereo)
    features = []
    count_number = 1

    for i in range(0, len(result_data), 2):
        if i + 1 < len(result_data):
            e1, e2 = result_data[i], result_data[i + 1]

            # ensure A/B columns always correspond to SpeakerA and SpeakerB
            if e1["source"] == "SpeakerB" and e2["source"] == "SpeakerA":
                e1, e2 = e2, e1

            # If both are same speaker (rare), keep order; fill missing as '/'
            a = e1 if e1["source"] == "SpeakerA" else None
            b = e2 if e2["source"] == "SpeakerB" else None

            if a is None and e1["source"] == "SpeakerA":
                a = e1
            if b is None and e2["source"] == "SpeakerB":
                b = e2

            # sanitize commas like old code
            if a:
                a_text = a["text"].replace(",", "*")
                dur_a, rate_a = calculate_speech_rate_words_s("SpeakerA", a["start"], a["text"], a["end"])
                a_count = 1
            else:
                a_text = "/"
                dur_a, rate_a = "/", "/"
                a_count = "/"

            if b:
                b_text = b["text"].replace(",", "*")
                dur_b, rate_b = calculate_speech_rate_words_s("SpeakerB", b["start"], b["text"], b["end"])
                b_count = 1
            else:
                b_text = "/"
                dur_b, rate_b = "/", "/"
                b_count = "/"

            features.append([
                f"{call_id}",
                f"{count_number}",
                f"\"{a_text}\"",
                f"{a_count}",
                f"{dur_a:.3f}" if isinstance(dur_a, float) else dur_a,
                f"{rate_a:.4f}" if isinstance(rate_a, float) else rate_a,
                f"\"{b_text}\"" if b_text != "/" else "/",
                f"{b_count}",
                f"{dur_b:.3f}" if isinstance(dur_b, float) else dur_b,
                f"{rate_b:.4f}" if isinstance(rate_b, float) else rate_b,
            ])
            count_number += 1
        else:
            e = result_data[i]
            if e["source"] == "SpeakerA":
                a_text = e["text"].replace(",", "*")
                dur_a, rate_a = calculate_speech_rate_words_s("SpeakerA", e["start"], e["text"], e["end"])
                features.append([
                    f"{call_id}", f"{count_number}",
                    f"\"{a_text}\"", "1",
                    f"{dur_a:.3f}", f"{rate_a:.4f}",
                    "/", "/", "/", "/"
                ])
            else:
                b_text = e["text"].replace(",", "*")
                dur_b, rate_b = calculate_speech_rate_words_s("SpeakerB", e["start"], e["text"], e["end"])
                features.append([
                    f"{call_id}", f"{count_number}",
                    "/", "/", "/", "/",
                    f"\"{b_text}\"", "1",
                    f"{dur_b:.3f}", f"{rate_b:.4f}",
                ])
            count_number += 1

    # ---- Find cut wavs for this call ----
    wav_files = [p.name for p in input_wav_directory.iterdir() if p.is_file() and p.name.startswith(call_id) and p.suffix.lower() == ".wav"]
    sorted_wavs = sorted(wav_files, key=extract_number)

    # ---- Run Praat stages ----
    # S1: placeholder 3, combined 6
    combined_s1 = run_stage_for_wavs(
        praat_script_name="S1.praat",
        wav_files=sorted_wavs,
        input_dir=input_wav_directory,
        output_dir=output_wav_directory,
        praat_bin=praat_path,
        placeholder_cols=3,
        pad_cols_if_missing=3,
        include_zero_arg=True,
    )
    # S2: placeholder 13, combined 26
    combined_s2 = run_stage_for_wavs(
        praat_script_name="S2.praat",
        wav_files=sorted_wavs,
        input_dir=input_wav_directory,
        output_dir=output_wav_directory,
        praat_bin=praat_path,
        placeholder_cols=13,
        pad_cols_if_missing=13,
        include_zero_arg=False,
    )
    # S3: placeholder 12, combined 24
    combined_s3 = run_stage_for_wavs(
        praat_script_name="S3.praat",
        wav_files=sorted_wavs,
        input_dir=input_wav_directory,
        output_dir=output_wav_directory,
        praat_bin=praat_path,
        placeholder_cols=12,
        pad_cols_if_missing=12,
        include_zero_arg=False,
    )
    # S4: placeholder 4, combined 8
    combined_s4 = run_stage_for_wavs(
        praat_script_name="S4.praat",
        wav_files=sorted_wavs,
        input_dir=input_wav_directory,
        output_dir=output_wav_directory,
        praat_bin=praat_path,
        placeholder_cols=4,
        pad_cols_if_missing=4,
        include_zero_arg=False,
    )

    # ---- Width guards (74 columns total) ----
    features = _normalize_rows_width(features, 10)
    combined_s1 = _normalize_rows_width(combined_s1, 6)
    combined_s2 = _normalize_rows_width(combined_s2, 26)
    combined_s3 = _normalize_rows_width(combined_s3, 24)
    combined_s4 = _normalize_rows_width(combined_s4, 8)

    merged = np.concatenate((features, combined_s1, combined_s2, combined_s3, combined_s4), axis=1)
    all_results.append(merged)


if not all_results:
    raise RuntimeError("No calls processed. Check your output_txt and output_cutwav folders.")

merged_features = np.vstack(all_results)

headers = [
    "Call_ID",
    "Time_ordered_segement",
    "Speaker_A_raw_text",
    "Speaker_A_speakCount",
    "Speaker_A_total_speak_time",
    "Speaker_A_speech_rate(words/s)",
    "Speaker_B_raw_text",
    "Speaker_B_speakCount",
    "Speaker_B_total_speak_time",
    "Speaker_B_speech_rate(words/s)",
    "Speaker_A_S1_decibels(intensity)",
    "Speaker_A_S1_mean_frequency",
    "Speaker_A_S1_frequency_SD",
    "Speaker_B_S1_decibels(intensity)",
    "Speaker_B_S1_mean_frequency",
    "Speaker_B_S1_frequency_SD",
    "Speaker_A_wav_ID_S2",
    "Speaker_A_S2_Mean_Intensity",
    "Speaker_A_S2_Intensity_SD",
    "Speaker_A_S2_Min_Intensity",
    "Speaker_A_S2_Max_Intensity",
    "Speaker_A_S2_05_Intensity",
    "Speaker_A_S2_95_Intensity",
    "Speaker_A_S2_Shimmer_Local",
    "Speaker_A_S2_Shimmer_Local_dB",
    "Speaker_A_S2_Shimmer_APQ3",
    "Speaker_A_S2_Shimmer_APQ5",
    "Speaker_A_S2_Shimmer_APQ11",
    "Speaker_A_S2_Shimmer_DDA",
    "Speaker_B_wav_ID_S2",
    "Speaker_B_S2_Mean_Intensity",
    "Speaker_B_S2_Intensity_SD",
    "Speaker_B_S2_Min_Intensity",
    "Speaker_B_S2_Max_Intensity",
    "Speaker_B_S2_05_Intensity",
    "Speaker_B_S2_95_Intensity",
    "Speaker_B_S2_Shimmer_Local",
    "Speaker_B_S2_Shimmer_Local_dB",
    "Speaker_B_S2_Shimmer_APQ3",
    "Speaker_B_S2_Shimmer_APQ5",
    "Speaker_B_S2_Shimmer_APQ11",
    "Speaker_B_S2_Shimmer_DDA",
    "Speaker_A_wav_ID_S3",
    "Speaker_A_S3_Min_Pitch",
    "Speaker_A_S3_Max_Pitch",
    "Speaker_A_S3_Mean_Pitch",
    "Speaker_A_S3_SD_Pitch",
    "Speaker_A_S3_QUP_Pitch",
    "Speaker_A_S3_QDown_Pitch",
    "Speaker_A_S3_Jitter_Local",
    "Speaker_A_S3_Jitter_Local_ABS",
    "Speaker_A_S3_Jitter_Rap",
    "Speaker_A_S3_Jitter_PPQ5",
    "Speaker_A_S3_Jitter_DDP",
    "Speaker_B_wav_ID_S3",
    "Speaker_B_S3_Min_Pitch",
    "Speaker_B_S3_Max_Pitch",
    "Speaker_B_S3_Mean_Pitch",
    "Speaker_B_S3_SD_Pitch",
    "Speaker_B_S3_QUP_Pitch",
    "Speaker_B_S3_QDown_Pitch",
    "Speaker_B_S3_Jitter_Local",
    "Speaker_B_S3_Jitter_Local_ABS",
    "Speaker_B_S3_Jitter_Rap",
    "Speaker_B_S3_Jitter_PPQ5",
    "Speaker_B_S3_Jitter_DDP",
    "Speaker_A_wav_ID_S4",
    "Speaker_A_S4_jitter_loc",
    "Speaker_A_S4_shimmer_loc",
    "Speaker_A_S4_HNR",
    "Speaker_B_wav_ID_S4",
    "Speaker_B_S4_jitter_loc",
    "Speaker_B_S4_shimmer_loc",
    "Speaker_B_S4_HNR",
]

tmp_csv = OUTPUT_DIR / "Test_feature_result_02.csv"
with tmp_csv.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(headers)
    w.writerows(merged_features)

df = pd.read_csv(tmp_csv, low_memory=False)

# column order: same as stereo
new_column_order = [
    "Call_ID",
    "Time_ordered_segement",
    "Speaker_A_raw_text",
    "Speaker_A_speakCount",
    "Speaker_A_total_speak_time",
    "Speaker_A_speech_rate(words/s)",
    "Speaker_A_S1_decibels(intensity)",
    "Speaker_A_S1_mean_frequency",
    "Speaker_A_S1_frequency_SD",
    "Speaker_A_wav_ID_S2",
    "Speaker_A_S2_Mean_Intensity",
    "Speaker_A_S2_Intensity_SD",
    "Speaker_A_S2_Min_Intensity",
    "Speaker_A_S2_Max_Intensity",
    "Speaker_A_S2_05_Intensity",
    "Speaker_A_S2_95_Intensity",
    "Speaker_A_S2_Shimmer_Local",
    "Speaker_A_S2_Shimmer_Local_dB",
    "Speaker_A_S2_Shimmer_APQ3",
    "Speaker_A_S2_Shimmer_APQ5",
    "Speaker_A_S2_Shimmer_APQ11",
    "Speaker_A_S2_Shimmer_DDA",
    "Speaker_A_wav_ID_S3",
    "Speaker_A_S3_Min_Pitch",
    "Speaker_A_S3_Max_Pitch",
    "Speaker_A_S3_Mean_Pitch",
    "Speaker_A_S3_SD_Pitch",
    "Speaker_A_S3_QUP_Pitch",
    "Speaker_A_S3_QDown_Pitch",
    "Speaker_A_S3_Jitter_Local",
    "Speaker_A_S3_Jitter_Local_ABS",
    "Speaker_A_S3_Jitter_Rap",
    "Speaker_A_S3_Jitter_PPQ5",
    "Speaker_A_S3_Jitter_DDP",
    "Speaker_A_wav_ID_S4",
    "Speaker_A_S4_jitter_loc",
    "Speaker_A_S4_shimmer_loc",
    "Speaker_A_S4_HNR",
    "Speaker_B_raw_text",
    "Speaker_B_speakCount",
    "Speaker_B_total_speak_time",
    "Speaker_B_speech_rate(words/s)",
    "Speaker_B_S1_decibels(intensity)",
    "Speaker_B_S1_mean_frequency",
    "Speaker_B_S1_frequency_SD",
    "Speaker_B_wav_ID_S2",
    "Speaker_B_S2_Mean_Intensity",
    "Speaker_B_S2_Intensity_SD",
    "Speaker_B_S2_Min_Intensity",
    "Speaker_B_S2_Max_Intensity",
    "Speaker_B_S2_05_Intensity",
    "Speaker_B_S2_95_Intensity",
    "Speaker_B_S2_Shimmer_Local",
    "Speaker_B_S2_Shimmer_Local_dB",
    "Speaker_B_S2_Shimmer_APQ3",
    "Speaker_B_S2_Shimmer_APQ5",
    "Speaker_B_S2_Shimmer_APQ11",
    "Speaker_B_S2_Shimmer_DDA",
    "Speaker_B_wav_ID_S3",
    "Speaker_B_S3_Min_Pitch",
    "Speaker_B_S3_Max_Pitch",
    "Speaker_B_S3_Mean_Pitch",
    "Speaker_B_S3_SD_Pitch",
    "Speaker_B_S3_QUP_Pitch",
    "Speaker_B_S3_QDown_Pitch",
    "Speaker_B_S3_Jitter_Local",
    "Speaker_B_S3_Jitter_Local_ABS",
    "Speaker_B_S3_Jitter_Rap",
    "Speaker_B_S3_Jitter_PPQ5",
    "Speaker_B_S3_Jitter_DDP",
    "Speaker_B_wav_ID_S4",
    "Speaker_B_S4_jitter_loc",
    "Speaker_B_S4_shimmer_loc",
    "Speaker_B_S4_HNR",
]
df = df[new_column_order]

# restore commas
df["Speaker_A_raw_text"] = df["Speaker_A_raw_text"].astype(str).str.replace("*", ",")
df["Speaker_B_raw_text"] = df["Speaker_B_raw_text"].astype(str).str.replace("*", ",")

# Final output required by runner/step6
out_csv = BASE_DIR / "audio_features_mono.csv"
df.to_csv(out_csv, index=False)

# cleanup
try:
    tmp_csv.unlink()
except Exception:
    pass

end_time = time.time()
end_datetime = datetime.fromtimestamp(end_time)
elapsed_datetime = end_datetime - start_datetime
print(f"Step05_audio_mono total running time: {elapsed_datetime} seconds")
print(f"Saved: {out_csv}")
