# AudioMatic

**AudioMatic** is an automated audio processing pipeline for extracting acoustic and linguistic features from speech recordings. It supports both mono and stereo audio, performs speaker diarization, transcription, and generates combined audio-text feature CSVs for downstream analysis.

> This code accompanies the paper:
Balducci, Bitty, Bin Pang, Lingshu Hu, Can Li, Wenbo Wang, Yi Shang, Detelina Marinova, and Matt Gordon. "Leveraging audio data: A guide to understanding customer-firm conversations." Marketing Letters 37, no. 1 (2026): 10.
https://doi.org/10.1007/s11002-025-09797-z

---

## Overview

AudioMatic processes `.wav` and `.mp3` audio files through a 6-step pipeline:

| Step | Script | Description |
|------|--------|-------------|
| 1 | `Step1_split_audio_unified.py` | Split long audio files into chunks |
| 2 | `Step2_wav_to_json_unified.py` | Transcribe with WhisperX + speaker diarization |
| 3 | `Step03_json_to_txt_mono.py` / `Step3_json_to_txt_stereo.py` | Convert JSON transcripts to speaker-turn TXT |
| 4 | `Step04_wav_cut_mono.py` / `Step4_wav_cut_stereo.py` | Cut WAV files by speaker turn |
| 5 | `Step05_generate_audio_features_txtbased_mono.py` / `Step5_generate_audio_features_txtbased_stereo.py` | Extract acoustic features per turn |
| 6 | `Step6_generate_text_features_combine_audio_text_features_unified.py` | Generate BERT text embeddings and combine with audio features |

The pipeline auto-detects whether each file is mono or stereo and routes it through the appropriate sub-pipeline. Final outputs are merged into a single CSV.

---

## Requirements

### System
- Linux (Ubuntu 20.04+ recommended)
- NVIDIA GPU with CUDA 11.8
- [Anaconda](Anaconda3-2024.10-1-Linux-x86_64.sh from https://repo.anaconda.com/archive)

### Hugging Face Account (required for diarization)
AudioMatic uses [pyannote.audio](https://github.com/pyannote/pyannote-audio) for speaker diarization, which requires accepting terms on two gated models:

1. Visit and accept: https://huggingface.co/pyannote/speaker-diarization-community-1
2. Visit and accept: https://huggingface.co/pyannote/segmentation-3.0

Then generate a **Read** token at: https://huggingface.co/settings/tokens

---

## Installation

### Step 0 - AudioMatic environment Setup

[AudioMatic - Linux GPU](https://docs.google.com/document/d/1tse4Jl7Ias5U56HKdHohNlgSM7SwDRdy3j9P-ulFLoQ/edit?tab=t.0)
[AUdioMatic - Windows GPU](https://docs.google.com/document/d/1ntQasMuE1ETGR4-N7YPuh45G0-l2nPo6LSuHM1Mq4eU/edit?tab=t.0)
[AudioMatic - Windows CPU](https://docs.google.com/document/d/1zyDpmOG69ohQ7I82KQoPwso9jH_rIUNfxJ4MoEBqc00/edit?tab=t.0)

### Step 1 — Clone the repository
```bash
git clone https://github.com/JoyPang528/AudioMatic
cd AudioMatic
```

### Step 2 — Create the conda environment
```bash
conda activate AudioMatic_Linux
```

> This installs PyTorch 2.0, WhisperX, pyannote, ffmpeg, sox, and all dependencies automatically. This may take 10–20 minutes depending on your internet speed.

### Step 3 — Set your Hugging Face token
```bash
export HUGGINGFACE_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxx"
```

To make it permanent (survives reboots):
```bash
echo 'export HUGGINGFACE_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxx"' >> ~/.bashrc
source ~/.bashrc
```
---

## Usage

### 1. Place your audio files in the `input/` folder
```
AudioMatic/
└── input/
    ├── recording1.wav
    ├── recording2.mp3
    └── ...
```

AudioMatic accepts `.wav` and `.mp3` files. Mono and stereo files can be mixed — the pipeline detects each automatically.

### 2. Run the pipeline
```bash
conda activate AudioMatic_Linux
python AudioMatic_unified.py
```

### 3. Find your results
```
AudioMatic/
├── audio_features.csv                    ← acoustic features
├── combine_audio_text_features.csv       ← audio + BERT text features combined
└── runs/
    └── 20260220_103000/                  ← timestamped archive of each run
        ├── audio_features.csv
        └── combine_audio_text_features.csv
```
---


## Output Format

### `audio_features.csv`
Contains acoustic features extracted per speaker turn.

### `combine_audio_text_features.csv`
Combines acoustic features with BERT-based text embeddings (768-dim) per speaker turn.

Both files include columns identifying the source file, speaker label (SpeakerA / SpeakerB), and timestamp.

---

## Troubleshooting

### `GatedRepoError: 403` during diarization
You need to accept pyannote model terms on Hugging Face. See [Requirements](#hugging-face-account-required-for-diarization).

Verify your token is set:
```bash
echo $HUGGINGFACE_TOKEN
python -c "from huggingface_hub import whoami; print(whoami())"
```

### Empty TXT output after Step 3
This means speaker labels are missing from the JSON. Make sure you ran Step 2 with `--diarize`:
```bash
python Step2_wav_to_json_unified.py --mode mono --diarize
```

### CUDA out of memory
Reduce batch size:
```bash
python Step2_wav_to_json_unified.py --mode mono --diarize --batch_size 2
```

### `av` build error / FFmpeg not found
FFmpeg is installed via conda in this environment. Make sure the conda env is activated:
```bash
conda activate AudioMatic_Linux
```

---

## Folder Structure

```
AudioMatic/
├── AudioMatic_unified.py                                         # Main pipeline orchestrator
├── Step1_split_audio_unified.py                                  # Step 1: split audio
├── Step2_wav_to_json_unified.py                                  # Step 2: transcribe + diarize
├── Step03_json_to_txt_mono.py                                    # Step 3: mono transcript
├── Step3_json_to_txt_stereo.py                                   # Step 3: stereo transcript
├── Step04_wav_cut_mono.py                                        # Step 4: mono wav cut
├── Step4_wav_cut_stereo.py                                       # Step 4: stereo wav cut
├── Step05_generate_audio_features_txtbased_mono.py               # Step 5: mono features
├── Step5_generate_audio_features_txtbased_stereo.py              # Step 5: stereo features
├── Step6_generate_text_features_combine_audio_text_features_unified.py  # Step 6: BERT + combine
├── environment.yml                                               # Conda environment spec
├── input/                                                        # Place audio files here
└── runs/                                                         # Timestamped run archives
```

---

## Citation

If you use AudioMatic in your research, please cite:
Balducci, B., Pang, B., Hu, L. et al. Leveraging audio data: A guide to understanding customer-firm conversations. Mark Lett 37, 10 (2026). https://doi.org/10.1007/s11002-025-09797-z
```

---

## License

This project is released under the [MIT License](LICENSE).

---

## Acknowledgements

- [WhisperX](https://github.com/m-bain/whisperX) — forced alignment and transcription
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) — speaker diarization
- [HuggingFace Transformers](https://github.com/huggingface/transformers) — BERT embeddings
- [SoX](http://sox.sourceforge.net/) — audio processing and feature extraction
- [Praat](https://www.fon.hum.uva.nl/praat/) — phonetic and acoustic analysis
