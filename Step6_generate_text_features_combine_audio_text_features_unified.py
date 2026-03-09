"""Step6_generate_text_features_combine_audio_text_features_unified_fixed.py


- Avoids the Transformers+TF safetensors bug that raises:
    TypeError: 'builtins.safe_open' object is not iterable
  by first trying to load TF model with safetensors disabled, and if TF load still fails,
  falling back to a PyTorch BERT model (torch is already used by WhisperX).

- Also suppresses TensorFlow CPU feature logs by setting TF_CPP_MIN_LOG_LEVEL
  BEFORE importing transformers/tensorflow.
"""

# ---- MUST be set before importing transformers/tensorflow ----
import os
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")         # hide TF info/warn
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")   # quieter tokenizer
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1") # hide download progress bars (optional)
# ------------------------------------------------------------

import warnings
warnings.filterwarnings("ignore")

import argparse
from pathlib import Path

import pandas as pd

# Try TF backend first (matches your previous implementation)
_BACKEND = None
tokenizer = None
model = None

def _load_bert():
    """Load BERT via PyTorch (TF support dropped in transformers 5.x)."""
    global _BACKEND, tokenizer, model
    import torch  # noqa: F401
    from transformers import AutoTokenizer, AutoModel
    from transformers.utils import logging as hf_logging
    hf_logging.set_verbosity_error()

    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    model = AutoModel.from_pretrained("bert-base-uncased")
    model.eval()
    _BACKEND = "pt"

_load_bert()

BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT", Path(__file__).resolve().parent)).resolve()
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_MONO_DIR = BASE_DIR / "output_mono"


def get_sentence_embedding(sentence, max_length=512):
    """Return 768-dim CLS embedding; for empty/'/' return '/' placeholders."""
    if sentence is None:
        return ["/"] * 768
    s = str(sentence)
    if (not s.strip()) or (s.strip() == "/"):
        return ["/"] * 768

    tokens = tokenizer.tokenize(tokenizer.decode(tokenizer.encode(s)))
    truncated_tokens = tokens[: max_length - 2]
    truncated_sequence = tokenizer.decode(tokenizer.convert_tokens_to_ids(truncated_tokens))

    if _BACKEND == "tf":
        tokens_tf = tokenizer(truncated_sequence, return_tensors="tf")
        outputs = model(**tokens_tf)
        cls_embedding = outputs.last_hidden_state[:, 0, :].numpy().flatten()
        return cls_embedding

    import torch
    with torch.no_grad():
        tokens_pt = tokenizer(truncated_sequence, return_tensors="pt")
        outputs = model(**tokens_pt)
        cls_embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy().flatten()
        return cls_embedding


def resolve_input_csv(mode: str) -> Path:
    if mode == "stereo":
        candidates = [
            BASE_DIR / "audio_features_stereo.csv",
            OUTPUT_DIR / "audio_features_stereo.csv",
            OUTPUT_DIR / "audio_features.csv",
        ]
    else:
        candidates = [
            BASE_DIR / "audio_features_mono.csv",
            OUTPUT_MONO_DIR / "audio_features.csv",
            OUTPUT_MONO_DIR / "audio_features_mono.csv",
        ]

    for p in candidates:
        if p.exists():
            return p

    raise FileNotFoundError(
        f"Cannot find input audio features CSV for mode={mode}. Tried: "
        + ", ".join(str(p) for p in candidates)
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["mono", "stereo"], required=True)
    args = ap.parse_args()

    speak_turns = resolve_input_csv(args.mode)
    df = pd.read_csv(str(speak_turns))

    df["A_embedding"] = df["Speaker_A_raw_text"].apply(lambda x: get_sentence_embedding(x))
    df["B_embedding"] = df["Speaker_B_raw_text"].apply(lambda x: get_sentence_embedding(x))

    A_embeddings = pd.DataFrame(df["A_embedding"].tolist(), columns=[f"A_{i}" for i in range(768)])
    B_embeddings = pd.DataFrame(df["B_embedding"].tolist(), columns=[f"B_{i}" for i in range(768)])

    df.drop(columns=["A_embedding", "B_embedding"], inplace=True)

    if "Speaker_A_S4_HNR" not in df.columns:
        raise KeyError("Column 'Speaker_A_S4_HNR' not found. Cannot insert A embeddings in the expected position.")
    if "Speaker_B_S4_HNR" not in df.columns:
        raise KeyError("Column 'Speaker_B_S4_HNR' not found. Cannot insert B embeddings in the expected position.")

    A_index = df.columns.get_loc("Speaker_A_S4_HNR") + 1
    df = pd.concat([df.iloc[:, :A_index], A_embeddings, df.iloc[:, A_index:]], axis=1)

    B_index = df.columns.get_loc("Speaker_B_S4_HNR") + 1 + 768
    df = pd.concat([df.iloc[:, :B_index], B_embeddings, df.iloc[:, B_index:]], axis=1)

    result_dir = Path(os.environ.get("AUDIOMATIC_RESULT_DIR", str(BASE_DIR))).resolve()
    result_dir.mkdir(parents=True, exist_ok=True)

    out_name = f"combine_audio_text_features_{args.mode}.csv"
    out_path = result_dir / out_name
    df.to_csv(str(out_path), index=False)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
