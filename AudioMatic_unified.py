"""
AudioMatic.py — Pipeline Orchestrator

Automatically detects mono/stereo audio files in the input/ folder
and routes them through the appropriate 6-step processing pipeline.

Usage:
    python AudioMatic.py                      # run full pipeline
    python AudioMatic.py --start-step 3       # resume from step 3
    python AudioMatic.py --keep-output-dirs   # keep intermediate folders
"""

import os
import shutil
import subprocess
import time
import sys
import argparse
from pathlib import Path


# ------------------------------------------------------------
# Paths (all relative to this script's directory)
# ------------------------------------------------------------
BASE_DIR        = str(Path(__file__).resolve().parent)
INPUT_DIR       = os.path.join(BASE_DIR, "input")
OUTPUT_DIR      = os.path.join(BASE_DIR, "output")
OUTPUT_MONO_DIR = os.path.join(BASE_DIR, "output_mono")
RESULT_PATH     = BASE_DIR

# Timestamped run archive
RUNS_DIR = os.path.join(BASE_DIR, "runs")
os.makedirs(RUNS_DIR, exist_ok=True)
run_id   = time.strftime("%Y%m%d_%H%M%S")
RUN_DIR  = os.path.join(RUNS_DIR, run_id)
os.makedirs(RUN_DIR, exist_ok=True)
ARCHIVE_PATH = RUN_DIR
print(f"[INFO] Run archive folder: {ARCHIVE_PATH}")


# ------------------------------------------------------------
# Step pipeline definitions
# ------------------------------------------------------------
MONO_SCRIPTS = [
    "Step1_split_audio_unified.py",
    ["Step2_wav_to_json_unified.py", "--mode", "mono", "--diarize"],
    "Step03_json_to_txt_mono.py",
    "Step04_wav_cut_mono.py",
    "Step05_generate_audio_features_txtbased_mono.py",
    ["Step6_generate_text_features_combine_audio_text_features_unified.py", "--mode", "mono"],
]

STEREO_SCRIPTS = [
    "Step1_split_audio_unified.py",
    ["Step2_wav_to_json_unified.py", "--mode", "stereo"],
    "Step3_json_to_txt_stereo.py",
    "Step4_wav_cut_stereo.py",
    "Step5_generate_audio_features_txtbased_stereo.py",
    ["Step6_generate_text_features_combine_audio_text_features_unified.py", "--mode", "stereo"],
]


# ------------------------------------------------------------
# Audio channel detection
# ------------------------------------------------------------
def is_stereo(file_path: str):
    """
    Return:
      True  -> stereo (>= 2 channels)
      False -> mono   (1 channel)
      None  -> unknown (detection failed)
    """
    # 1) Try soxi (fast, reliable if sox installed)
    for cmd in (["soxi", "-c", file_path], ["sox", "--i", "-c", file_path]):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, check=True)
            ch = int(r.stdout.strip().splitlines()[-1])
            return ch >= 2
        except Exception:
            pass

    # 2) ffprobe (handles MP3, WAV, FLAC, M4A, OGG)
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=channels",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True, text=True, check=True,
        )
        ch = int(r.stdout.strip())
        return ch >= 2
    except Exception:
        pass

    print(f"[WARN] Cannot detect channels for: {file_path}")
    return None


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def normalize_hf_token(env: dict) -> str:
    """Ensure all HF token env var names are set consistently."""
    keys = ["HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACEHUB_API_TOKEN"]
    token = ""
    for k in keys:
        v = env.get(k, "").strip()
        if v:
            token = v
            break
    if token:
        for k in keys:
            env[k] = token
    return token


def cleanup_output_dirs():
    """Delete intermediate output directories."""
    for dir_path in [OUTPUT_MONO_DIR, OUTPUT_DIR]:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)


def cleanup_old_results():
    """Delete old result CSVs from previous runs."""
    for name in [
        "audio_features_mono.csv",
        "audio_features_stereo.csv",
        "audio_features.csv",
        "combine_audio_text_features_mono.csv",
        "combine_audio_text_features_stereo.csv",
        "combine_audio_text_features.csv",
    ]:
        fp = os.path.join(RESULT_PATH, name)
        if os.path.exists(fp):
            os.remove(fp)


def merge_csv(input_files, output_file, delete_inputs=False):
    """Merge multiple CSV files into one, skipping duplicate headers."""
    with open(output_file, "w", encoding="utf-8") as outfile:
        for i, file in enumerate(input_files):
            if os.path.exists(file):
                with open(file, "r", encoding="utf-8", errors="ignore") as infile:
                    if i != 0:
                        next(infile, None)  # skip header on subsequent files
                    outfile.writelines(infile)
    if delete_inputs:
        for file in input_files:
            if os.path.exists(file):
                os.remove(file)


def rename_and_merge_outputs():
    """
    Merge per-mode CSVs into final output files:
      - audio_features.csv
      - combine_audio_text_features.csv
    """
    audio_mono     = os.path.join(RESULT_PATH, "audio_features_mono.csv")
    audio_stereo   = os.path.join(RESULT_PATH, "audio_features_stereo.csv")
    combine_mono   = os.path.join(RESULT_PATH, "combine_audio_text_features_mono.csv")
    combine_stereo = os.path.join(RESULT_PATH, "combine_audio_text_features_stereo.csv")
    audio_final    = os.path.join(RESULT_PATH, "audio_features.csv")
    combine_final  = os.path.join(RESULT_PATH, "combine_audio_text_features.csv")

    for f in [audio_final, combine_final]:
        if os.path.exists(f):
            os.remove(f)

    audio_inputs   = [p for p in [audio_mono, audio_stereo] if os.path.exists(p)]
    combine_inputs = [p for p in [combine_mono, combine_stereo] if os.path.exists(p)]

    if len(audio_inputs) == 2:
        merge_csv(audio_inputs, audio_final)
    elif len(audio_inputs) == 1:
        shutil.copy2(audio_inputs[0], audio_final)

    if len(combine_inputs) == 2:
        merge_csv(combine_inputs, combine_final)
    elif len(combine_inputs) == 1:
        shutil.copy2(combine_inputs[0], combine_final)

    # Remove per-mode files — only keep finals
    for f in [audio_mono, audio_stereo, combine_mono, combine_stereo]:
        if os.path.exists(f):
            os.remove(f)


def archive_run_outputs():
    """Copy final CSVs into the timestamped run archive folder."""
    os.makedirs(ARCHIVE_PATH, exist_ok=True)
    for name in ["audio_features.csv", "combine_audio_text_features.csv"]:
        src = os.path.join(RESULT_PATH, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(ARCHIVE_PATH, name))


# ------------------------------------------------------------
# Step runner
# ------------------------------------------------------------
def run_step(script, tail_lines=12):
    """
    Run a pipeline step script using the current Python interpreter.
    Captures output and prints only the last few lines on error.
    """
    env = os.environ.copy()
    normalize_hf_token(env)
    env["TF_CPP_MIN_LOG_LEVEL"] = "3"
    env["AUDIOMATIC_ROOT"] = BASE_DIR
    env["AUDIOMATIC_RESULT_DIR"] = RESULT_PATH

    if isinstance(script, (list, tuple)):
        script_name, args = script[0], list(script[1:])
    else:
        script_name, args = script, []

    cmd = [sys.executable, script_name] + args
    result = subprocess.run(
        cmd, cwd=BASE_DIR, env=env, text=True, capture_output=True
    )

    if result.returncode != 0:
        msg  = (result.stderr or result.stdout or "").strip()
        tail = "\n".join(msg.splitlines()[-tail_lines:]) if msg else "(no output)"
        print(f"[ERROR] {script_name} failed (exit {result.returncode}).")
        print(tail)
        raise RuntimeError(f"{script_name} failed with exit code {result.returncode}")

    return result.stdout


# ------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------
def process_files(start_step=1, skip_cleanup_start=False, keep_output_dirs=False):
    if not os.path.exists(INPUT_DIR):
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    files = [
        os.path.join(INPUT_DIR, f)
        for f in os.listdir(INPUT_DIR)
        if f.lower().endswith((".wav", ".mp3"))
    ]

    if not files:
        print(f"[WARN] No .wav or .mp3 files found in: {INPUT_DIR}")
        return

    # Sort files into mono / stereo
    mono_files, stereo_files = [], []
    for f in files:
        s = is_stereo(f)
        if s is True:
            stereo_files.append(f)
        elif s is False:
            mono_files.append(f)
        else:
            # Unknown — process through both pipelines to be safe
            mono_files.append(f)
            stereo_files.append(f)

    print(f"[INFO] Found {len(mono_files)} mono, {len(stereo_files)} stereo file(s).")

    if not skip_cleanup_start:
        cleanup_output_dirs()
        cleanup_old_results()

    start_time = time.time()
    had_error  = False
    mono_ok    = True
    stereo_ok  = True

    # ---- MONO pipeline ----
    if mono_files:
        print("[INFO] Starting mono pipeline...")
        for i, s in enumerate(MONO_SCRIPTS, start=1):
            if i < start_step:
                continue
            try:
                run_step(s)
            except Exception as e:
                had_error = True
                mono_ok   = False
                print(f"[ERROR] Mono Step {i} failed: {e}")
                break

    # ---- STEREO pipeline ----
    if stereo_files:
        print("[INFO] Starting stereo pipeline...")
        for i, s in enumerate(STEREO_SCRIPTS, start=1):
            if i < start_step:
                continue
            try:
                run_step(s)
            except Exception as e:
                had_error  = True
                stereo_ok  = False
                print(f"[ERROR] Stereo Step {i} failed: {e}")
                break

    # Merge and archive outputs
    if mono_ok or stereo_ok:
        try:
            rename_and_merge_outputs()
        except Exception as e:
            had_error = True
            print(f"[ERROR] merge outputs failed: {e}")
        try:
            archive_run_outputs()
        except Exception as e:
            had_error = True
            print(f"[ERROR] archive outputs failed: {e}")
    else:
        print("[ERROR] Both pipelines failed. No outputs to merge.")

    if not (had_error or keep_output_dirs):
        cleanup_output_dirs()

    elapsed = time.time() - start_time
    print(f"[INFO] Run archive folder: {ARCHIVE_PATH}")
    print(f"[INFO] Total running time: {int(elapsed // 60)} min {elapsed % 60:.2f} sec")


def main():
    parser = argparse.ArgumentParser(
        description="AudioMatic — Automated Audio Processing Pipeline"
    )
    parser.add_argument(
        "--start-step", type=int, default=1, choices=[1, 2, 3, 4, 5, 6],
        help="Resume from this step (default: 1)."
    )
    parser.add_argument(
        "--skip-cleanup-start", action="store_true",
        help="Do not delete previous output folders at start (use when resuming)."
    )
    parser.add_argument(
        "--keep-output-dirs", action="store_true",
        help="Keep intermediate output folders after completion."
    )
    args = parser.parse_args()

    skip_cleanup = args.skip_cleanup_start or (args.start_step > 1)
    process_files(
        start_step=args.start_step,
        skip_cleanup_start=skip_cleanup,
        keep_output_dirs=args.keep_output_dirs,
    )


if __name__ == "__main__":
    main()
