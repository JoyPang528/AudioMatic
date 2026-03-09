
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
from typing import List, Union



"""
The input are the generated txt files.
The output is a audio features csv file.

"""
#print("Begin to run Step5_generate_audio_features_txtbased, generate audio features file...")

start_time = time.time()
start_datetime = datetime.fromtimestamp(start_time)

# Server sets AUDIOMATIC_WORKDIR; package users don't need to.
# BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT", Path(__file__).resolve().parent)).resolve()
BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT") or Path.cwd()).resolve()


OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Specify the directory containing your JSON files

# Create an output directory if it doesn't exist

# result_path = './output'
result_path = OUTPUT_DIR
# os.makedirs(result_path, exist_ok=True)

# directory_path = './output/output_txt_1'
directory_path = result_path / "output_txt_1"

# praat_path = './praat'
praat_path = BASE_DIR / ("praat.exe" if platform.system()=="Windows" else "praat")

# input_wav_directory = './output/output_cutwav'
input_wav_directory = result_path / "output_cutwav"


# output_wav_directory = './output/output_csv'
output_wav_directory = result_path / "output_csv"
# os.makedirs(output_wav_directory, exist_ok = True)
output_wav_directory.mkdir(parents=True, exist_ok=True)

# Initialize a count for generated files
file_count = 0
skipped_file_count = 0

# Initialize an empty dictionary to store pairs of documents
document_pairs = {}

# List to store names of skipped pairs
skipped_pairs = []

merged_features_02 = np.empty((0, 74))



# List all files in the directory
all_files_02 = os.listdir(directory_path)
#print(all_files_02)
#print("****")

# Filter files based on the second part being "_result" and ending with ".txt"
result_files_02 = [file for file in all_files_02 if file.endswith('__result.txt')]
#print(result_files_02)
# Create a dictionary to map first parts to corresponding files
file_dict_02 = {}
for file_name in result_files_02:
    #first_part = file_name.split('__')[0]
    first_part = re.sub(r'__result\.txt$', '', file_name)
    
    file_path = os.path.join(directory_path, file_name)
    #print(file_path)
    #print("___")
    
    if first_part not in file_dict_02:
        file_dict_02[first_part] = file_path
#print(file_dict_02)
#print("&&&")
        
def extract_data_from_line(line):
    # Define a regular expression pattern to match the required information
    pattern = r'(?P<source>Customer|Salesperson): \[(?P<start>[\d:]+)\] (?P<text>.+?) \[(?P<end>[\d:]+)\] (?P<count_data>\d+)'

    
    # Use re.match to apply the pattern to the line
    match = re.match(pattern, line)
    
    # If the pattern matches, extract the groups and create a dictionary
    if match:
        data = match.groupdict()
        return data
    else:
        return None

def process_txt_file(file_path):
    result = []
    with open(file_path, 'r') as file:
        for line in file:
            # Process each line in the file
            extracted_data = extract_data_from_line(line)
            if extracted_data:
                result.append(extracted_data)

    return result

# Function to read the file
def read_file(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            if not content.strip():  # Check if the content is empty or only contains whitespace
                print(f"The file '{file_path}' is empty. Skipping...")
                return None
            else:
                #print(f"Contents of the file '{file_path}':")
                #print(content)
                return content
    except FileNotFoundError:
        print(f"The file '{file_path}' does not exist. Skipping...")
        return None
    
all_results = []


def _normalize_rows_width(rows, width, fill_value="/"):
    """Ensure a 2D list/array has exactly `width` columns by truncating/padding each row."""
    fixed = []
    for r in rows:
        # allow numpy arrays / tuples
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

    if praat_bin.exists():
        cmd = [str(praat_bin), "--run", str(script_path)] + [str(a) for a in args]
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if p.returncode == 0:
                return "praat_bin"
            if verbose:
                print(f"[WARN] Praat bin failed (code={p.returncode}) for: {' '.join(cmd)}\n{(p.stderr or '')[:300]}")
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
    """Read the single-row CSV output as a list of values (keeps your original split(',') behavior)."""
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



# Process and generate results for each document
for mutual_part_02, txt_file_path_02 in file_dict_02.items():
    
    read_file(txt_file_path_02)
    
    result_data_02 = process_txt_file(txt_file_path_02)
    
    features_02 = []
    count_number = 1  # Initialize the count number
    


    def calculate_speech_rate_words_s(sentence):
        speaker, start_time, text, end_time = sentence
        start_time = start_time.split(":")
        end_time = end_time.split(":")
        start_seconds = (int(start_time[0]) * 60) + int(start_time[1]) + (int(start_time[2]) / 1000)
        end_seconds = (int(end_time[0]) * 60) + int(end_time[1]) + (int(end_time[2]) / 1000)
        
        duration = end_seconds - start_seconds
        words = len(text.split())
        if duration > 0:
            speech_rate_words_s = words / duration
        else:
            speech_rate_words_s = 0
        return duration, speech_rate_words_s

    for i in range(0, len(result_data_02), 2):
        if i + 1 < len(result_data_02):
            entry1 = result_data_02[i]
            entry2 = result_data_02[i + 1]
            count_data1 = entry1["count_data"]
            count_data2 = entry2["count_data"]
            
            line_pattern = r"(\w+): (\d+:\d+:\d+) (.+) (\d+:\d+:\d+)"
            
            sentence1 = f"{entry1['source']}: {entry1['start']} {entry1['text']} {entry1['end']}"
            match = re.match(line_pattern, sentence1)
            if match:
                speaker, start_time, text, end_time = match.groups()
                sentence1 = [speaker, start_time, text, end_time]
            #print(sentence1)
                
            sentence2 = f"{entry2['source']}: {entry2['start']} {entry2['text']} {entry2['end']}"
            match = re.match(line_pattern, sentence2)
            if match:
                speaker, start_time, text, end_time = match.groups()
                sentence2 = [speaker, start_time, text, end_time]
            
            duration1, speech_rate_words_s1 = calculate_speech_rate_words_s(sentence1)
            duration2, speech_rate_words_s2 = calculate_speech_rate_words_s(sentence2)

            #row1 = f'{entry1["text"]}'
            #row2 = f'{entry2["text"]}'
            entry1["text"] = entry1["text"].replace(",", "*")
            entry2["text"] = entry2["text"].replace(",", "*")
         
            features_02.append([f'{mutual_part_02}', f'{count_number}', f'"{entry1["text"]}"', f'{count_data1}', f'{duration1:.3f}', 
                            f'{speech_rate_words_s1:.4f}', f'"{entry2["text"]}"', f'{count_data2}', f'{duration2:.3f}', 
                            f'{speech_rate_words_s2:.4f}'])

            count_number += 1
            
        else:  # Handle the last odd entry
            entry = result_data_02[i]
            count_data = entry["count_data"]
            line_pattern = r"(\w+): (\d+:\d+:\d+) (.+) (\d+:\d+:\d+)"
            sentence = f"{entry['source']}: {entry['start']} {entry['text']} {entry['end']}"
            match = re.match(line_pattern, sentence)
            if match:
                speaker, start_time, text, end_time = match.groups()
                sentence = [speaker, start_time, text, end_time]
                
            
            duration, speech_rate_words_s = calculate_speech_rate_words_s(sentence)
            entry["text"] = entry["text"].replace(",", "*")
            

            features_02.append([f'{mutual_part_02}', f'{count_number}', f'"{entry["text"]}"', f'{count_data}', f'{duration:.3f}', 
                            f'{speech_rate_words_s:.4f}', '/', '/', '/', '/'])


    #print(merged_features_02)
    #print(features_02)
    #print("\n")
    #print("+++++")
    
    def remove_files_in_directory(directory__path):
        try:
            # Iterate through all files in the directory
            for filename in os.listdir(directory__path):
                file_path = os.path.join(directory__path, filename)
    
                # Check if the path is a file
                if os.path.isfile(file_path):
                    # Remove the file
                    os.remove(file_path)
                    #print(f"Removed file: {file_path}")
    
            #print(f"All files in {directory__path} have been removed.")
        except Exception as e:
            print(f"Error: {e}")
    # Extract the number that appears right before "_Salesperson" or "_Customer"
    def extract_number(filename):
        match = re.search(r'__(\d+)(?=_Salesperson|_Customer)', filename)
        return int(match.group(1)) if match else float('inf')  # Assign inf if no match is found
    

    # List all CSV files in the directory
    wav_files_02 = [file for file in os.listdir(input_wav_directory) if file.startswith(f"{mutual_part_02}")]

    # Sort files based on extracted numbers
    sorted_wav_files_02 = sorted(wav_files_02, key=extract_number)

    # Run Praat stages efficiently (try praat --run first, fallback to parselmouth.run_file)
    # Per-segment CSV widths (A channel) inferred from your correct sample output:
    #   S1: 3  -> combined A+B = 6
    #   S2: 13 -> combined A+B = 26
    #   S3: 12 -> combined A+B = 24
    #   S4: 4  -> combined A+B = 8
    combined_data_F0_02 = run_stage_for_wavs(
        praat_script_name="S1.praat",
        wav_files=sorted_wav_files_02,
        input_dir=Path(input_wav_directory),
        output_dir=Path(output_wav_directory),
        praat_bin=Path(praat_path),
        placeholder_cols=3,
        pad_cols_if_missing=3,
        include_zero_arg=True,
    )

    combined_data_S1_02 = run_stage_for_wavs(
        praat_script_name="S2.praat",
        wav_files=sorted_wav_files_02,
        input_dir=Path(input_wav_directory),
        output_dir=Path(output_wav_directory),
        praat_bin=Path(praat_path),
        placeholder_cols=13,
        pad_cols_if_missing=13,
        include_zero_arg=False,
    )

    combined_data_S2_02 = run_stage_for_wavs(
        praat_script_name="S3.praat",
        wav_files=sorted_wav_files_02,
        input_dir=Path(input_wav_directory),
        output_dir=Path(output_wav_directory),
        praat_bin=Path(praat_path),
        placeholder_cols=12,
        pad_cols_if_missing=12,
        include_zero_arg=False,
    )

    combined_data_S3_02 = run_stage_for_wavs(
        praat_script_name="S4.praat",
        wav_files=sorted_wav_files_02,
        input_dir=Path(input_wav_directory),
        output_dir=Path(output_wav_directory),
        praat_bin=Path(praat_path),
        placeholder_cols=4,
        pad_cols_if_missing=4,
        include_zero_arg=False,
    )

# ---- Width guards to avoid intermittent vstack failures ----
    # Expected column widths (must sum to 74 headers)
    features_02 = _normalize_rows_width(features_02, 10)
    combined_data_F0_02 = _normalize_rows_width(combined_data_F0_02, 6)
    combined_data_S1_02 = _normalize_rows_width(combined_data_S1_02, 26)
    combined_data_S2_02 = _normalize_rows_width(combined_data_S2_02, 24)
    combined_data_S3_02 = _normalize_rows_width(combined_data_S3_02, 8)
    # ------------------------------------------------------------
    merged_array_02 = np.concatenate((features_02, combined_data_F0_02, combined_data_S1_02, combined_data_S2_02, combined_data_S3_02), axis=1)

    # Append to list
    all_results.append(merged_array_02)
    
# Final concatenation after the loop
merged_features_02 = np.vstack(all_results)  # Stack all results at once (efficient)
#print(merged_features_02)


# List of headers
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
    "Speaker_B_S4_HNR"
]

# Create a features_02 CSV file and write the headers as the first row
features_02_filename = os.path.join(result_path, "Test_feature_result_02.csv")
with open(features_02_filename, 'w', newline='') as output_file:
    writer = csv.writer(output_file)
    
    # Write the headers as the first row
    writer.writerow(headers)
    
    # Write the existing data back into the new file
    writer.writerows(merged_features_02)
    
# Read the CSV file into a DataFrame

df = pd.read_csv(features_02_filename, low_memory=False)


# Specify the order of the columns as per your requirement
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
    "Speaker_B_S4_HNR"
]

# Reorder the columns
df = df[new_column_order]

# Convert columns to strings and replace "*" with ","
df['Speaker_A_raw_text'] = df['Speaker_A_raw_text'].astype(str).str.replace('*', ',')
df['Speaker_B_raw_text'] = df['Speaker_B_raw_text'].astype(str).str.replace('*', ',')

    
# Write the DataFrame back to a new CSV file
# df.to_csv('./audio_features_stereo.csv', index=False)
df.to_csv(str(BASE_DIR / "audio_features_stereo.csv"), index=False)

    
    # Record the end time
end_time = time.time()
end_datetime = datetime.fromtimestamp(end_time)
    

os.remove(features_02_filename)



# Calculate the elapsed time
#elapsed_time = format_time(end_time - start_time)

#print(f"Total running time: {elapsed_time} seconds")

#print(start_datetime)
#print(end_datetime)

elapsed_datetime = end_datetime - start_datetime
#print(f"Step5_generate_audio_features_txtbased total running time: {elapsed_datetime} seconds")
