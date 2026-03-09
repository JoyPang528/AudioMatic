"""
Step2_wav_to_json_unified.py (mono + stereo)

Purpose
- Run WhisperX on split WAV files and output JSON files.
- Supports BOTH stereo and mono pipelines by switching --mode.
- Hugging Face token is OPTIONAL unless diarization is enabled.
  Accepted env var names:
    - HF_TOKEN
    - HUGGINGFACE_TOKEN
    - HUGGINGFACEHUB_API_TOKEN

Folder conventions (relative to the REAL working directory):
  stereo: output/split       -> output/output_json
  mono:   output_mono/split  -> output_mono/output_json

Notes
- We call WhisperX via:  python -m whisperx
  (more robust than relying on the "whisperx" CLI being on PATH)
"""

from __future__ import annotations

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Optional, Tuple


# Quiet common logs (must be set before TF/transformers get imported by WhisperX)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("PYTHONWARNINGS", "ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def is_cuda_oom(err: str) -> bool:
    e = (err or "").lower()
    return ("out of memory" in e) or ("cuda" in e) or ("cublas" in e)


def get_hf_token() -> str:
    """
    Read a Hugging Face token from common environment variable names.
    Does NOT print the token. Returns "" if not found.
    """
    for k in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACEHUB_API_TOKEN"):
        v = os.environ.get(k, "").strip()
        if v:
            # Normalize for downstream tools
            os.environ["HF_TOKEN"] = v
            os.environ["HUGGINGFACE_TOKEN"] = v
            os.environ["HUGGINGFACEHUB_API_TOKEN"] = v
            return v
    return ""


def _tail(text: str, n: int = 8) -> str:
    lines = (text or "").splitlines()
    return "\n".join(lines[-n:]) if lines else ""


def run_whisperx_one(
    wav_path: Path,
    out_dir: Path,
    hf_token: str,
    batch_size: int,
    compute_type: str,
    diarize: bool,
    max_speakers: Optional[int],
    model: str,
    align_model: str,
    language: str,
    extra_args: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """
    Returns (ok, stderr_text).
    """
    cmd: List[str] = [
        sys.executable, "-m", "whisperx",
        str(wav_path),
        "--model", model,
        "--align_model", align_model,
        "--batch_size", str(batch_size),
        "--language", language,
        "--compute_type", compute_type,
        "--output_dir", str(out_dir),
        "--output_format", "json",
    ]

    # Only pass token if we actually have one.
    # (Diarization typically requires a token; non-diarization usually does not.)
    if hf_token:
        cmd += ["--hf_token", hf_token]

    if diarize:
        cmd.append("--diarize")
        if max_speakers is not None:
            cmd += ["--max_speakers", str(max_speakers)]

    if extra_args:
        cmd += extra_args

    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if p.returncode == 0:
        return True, ""
    return False, (p.stderr or "")


def main() -> None:
    # IMPORTANT: In PyInstaller runs, __file__ may be in a _MEI temp dir.
    # Use AUDIOMATIC_ROOT if provided; otherwise use the current working directory
    # (the wrapper should run us with cwd=BASE_DIR).
    base_dir = Path(os.environ.get("AUDIOMATIC_ROOT") or Path.cwd()).resolve()

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mode",
        choices=["stereo", "mono"],
        default="stereo",
        help="Which pipeline folders to use: stereo uses output/, mono uses output_mono/",
    )
    ap.add_argument("--diarize", action="store_true", help="Enable diarization (recommended for mono).")
    ap.add_argument(
        "--max_speakers",
        type=int,
        default=None,
        help="Max speakers for diarization (e.g., 3). Used only when --diarize is set.",
    )
    ap.add_argument("--batch_size", type=int, default=4, help="Initial batch size (reduce if you hit OOM).")
    ap.add_argument(
        "--fallback_batch_size", type=int, default=1, help="Fallback batch size used after OOM-like errors."
    )
    ap.add_argument("--compute_type", type=str, default="float32", help="WhisperX compute_type.")
    ap.add_argument("--model", type=str, default="large-v2", help="Whisper model name (e.g., large-v2, medium).")
    ap.add_argument("--align_model", type=str, default="WAV2VEC2_ASR_LARGE_LV60K_960H", help="Alignment model name.")
    ap.add_argument("--language", type=str, default="en", help="Language code, e.g., en")
    args, unknown = ap.parse_known_args()

    hf_token = get_hf_token()

    # Only require token when diarization is enabled.
    if args.diarize and not hf_token:
        print("[ERROR] Missing Hugging Face token. Set HF_TOKEN (or HUGGINGFACE_TOKEN) and re-run.")
        sys.exit(1)

    out_root = base_dir / ("output_mono" if args.mode == "mono" else "output")
    wav_split_dir = out_root / "split"
    json_out_dir = out_root / "output_json"
    json_out_dir.mkdir(parents=True, exist_ok=True)

    if not wav_split_dir.exists():
        print(f"[ERROR] split directory does not exist: {wav_split_dir}")
        sys.exit(1)

    wav_files = sorted([p for p in wav_split_dir.iterdir() if p.is_file() and p.suffix.lower() == ".wav"])
    if not wav_files:
        print(f"[ERROR] No .wav files found in: {wav_split_dir}")
        sys.exit(1)

    fail_count = 0
    for wav_path in wav_files:
        ok, err = run_whisperx_one(
            wav_path=wav_path,
            out_dir=json_out_dir,
            hf_token=hf_token,
            batch_size=args.batch_size,
            compute_type=args.compute_type,
            diarize=args.diarize,
            max_speakers=args.max_speakers,
            model=args.model,
            align_model=args.align_model,
            language=args.language,
            extra_args=unknown,
        )

        if (not ok) and is_cuda_oom(err):
            ok, err = run_whisperx_one(
                wav_path=wav_path,
                out_dir=json_out_dir,
                hf_token=hf_token,
                batch_size=args.fallback_batch_size,
                compute_type=args.compute_type,
                diarize=args.diarize,
                max_speakers=args.max_speakers,
                model=args.model,
                align_model=args.align_model,
                language=args.language,
                extra_args=unknown,
            )

        # Sanity check: whisperx should create <stem>.json in output_dir
        expected = json_out_dir / f"{wav_path.stem}.json"
        if ok and not expected.exists():
            # Some whisperx versions may name slightly differently; check for any json created.
            # If none, treat as failure.
            if not any(json_out_dir.glob("*.json")):
                ok = False
                err = (err or "") + f"\nNo JSON output detected in {json_out_dir}"

        if not ok:
            fail_count += 1
            # Keep logs short: print only last line/tail
            tail = _tail(err, n=6)
            if tail:
                print(f"[ERROR] WhisperX failed for {wav_path.name}:\n{tail}")
            else:
                print(f"[ERROR] WhisperX failed for {wav_path.name} (no stderr).")

    # If anything failed, stop with non-zero code so the wrapper won't proceed to Step3.
    if fail_count:
        print(f"[ERROR] Step2 failed for {fail_count}/{len(wav_files)} file(s).")
        sys.exit(1)

    # Final guard: ensure something was produced
    if not any(json_out_dir.glob("*.json")):
        print(f"[ERROR] Step2 produced no JSON files in: {json_out_dir}")
        sys.exit(1)


if __name__ == "__main__":
    main()
