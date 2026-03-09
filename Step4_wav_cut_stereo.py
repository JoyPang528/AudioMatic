import re
import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path
import shutil
import platform

start_time = time.time()
start_datetime = datetime.fromtimestamp(start_time)

#print("Begin to run Step4_wav_cut, Cutting wav files...")

# Server sets AUDIOMATIC_WORKDIR; package users don't need to.
# BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT", Path(__file__).resolve().parent)).resolve()
BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT") or Path.cwd()).resolve()


OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Resolve SoX binary (Windows: tools/sox.exe; Linux: tools/sox or system sox)
if platform.system() == "Windows":
    SOX_BIN = str(BASE_DIR / "tools" / "sox.exe")
else:
    bundled = BASE_DIR / "tools" / "sox"
    if bundled.exists():
        SOX_BIN = str(bundled)
    else:
        SOX_BIN = shutil.which("sox") or "sox"




directory_path = OUTPUT_DIR / "output_txt_1"
# directory_path = './output/output_txt_1'

# Check if the directory is empty
if not os.path.exists(directory_path) or not os.listdir(directory_path):
    print(f"Error: The directory '{directory_path}' is empty or does not exist. Please ensure it contains files before proceeding.")
    sys.exit(1)  # Exit the program with an error code


#replace your own path to the directory containing the audios which need to be cut
#wav_split_path = r'D:\wav_leftright_1'
# wav_split_path = './output/split'
wav_split_path = OUTPUT_DIR / "split"


#result_path = r'D:\wav_cut_test_2'
# result_path = './output/output_cutwav'
result_path = OUTPUT_DIR / "output_cutwav"
# os.makedirs(result_path, exist_ok = True)
result_path.mkdir(parents=True, exist_ok=True)



def create_name_match_dict(folder_path):
    NameMatch = {}
    if not os.path.exists(folder_path):
        print(f"Error: The folder {folder_path} does not exist.")
        return NameMatch
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            file_name_without_extension = os.path.splitext(filename)[0]
            file_name_fix = re.sub(r'[^a-zA-Z0-9]', '', file_name_without_extension)
            NameMatch[file_name_fix] = filename
    return NameMatch

def file_lookup(filename,NameMatch):
    file_name_without_extension = os.path.splitext(filename)[0]
    file_name_fix = re.sub(r'[^a-zA-Z0-9]', '', file_name_without_extension)
    if file_name_fix in NameMatch:
        return NameMatch[file_name_fix]
    else:
        return None
        
NameMatch = create_name_match_dict(folder_path=wav_split_path) #Run only once!!!



last_result = None  # keep last sox run result
sox_failures = 0
sox_runs = 0
def convert_time_format(time_str):
    # Convert the time format from "00:00:000" to "00m00.000s"
    minutes, seconds, milliseconds = re.split('[:.]', time_str)
    return f'{minutes}m{seconds.zfill(2)}.{milliseconds.zfill(3)}s'


def convert_time_format_2(time_str):
    # Convert the time format from "00:00:000" to "00*60+00.000s"
    minutes, seconds, milliseconds = re.split('[:.]', time_str)
    total_seconds = int(minutes) * 60 + int(seconds)
    return f'{total_seconds}.{milliseconds.zfill(3)}'
    

# Iterate through each file in the directory
for filename in os.listdir(directory_path):
        
    if filename.endswith("__result.txt"):  # Ensure it's a text document with "result" at the end
        # Extract the filename without "result" at the end
        document_name = filename[:-len("__result.txt")]

        file_path = os.path.join(directory_path, filename)

        # Open and read the file
        with open(file_path, 'r', errors = 'ignore') as file:
            
            lines = file.readlines()
        
            # Initialize variables to keep track of line number
            line_number = 0
            line_written = False
            # Iterate through each line and extract the desired information
            for line in lines:
                line = line.strip()  # Remove leading/trailing whitespace
                match = re.match(r'(\w+): \[(\d+:\d+:\d+)\] (.+?) \[(\d+:\d+:\d+)\]', line)
                if match:
                    line_number += 1
                    speaker = match.group(1)
                    time1 = convert_time_format(match.group(2))
                    time2 = convert_time_format(match.group(4))
                    time3 = convert_time_format_2(match.group(2))
                    time4 = convert_time_format_2(match.group(4))
                    
                    text1 = match.group(3)
                    
                    formatted_numbers = str(line_number).zfill(3)
            
                    #print(f"Line {line_number}: Speaker: {speaker}, Time 1: {time1}, Text 1: {text1}, Time 2: {time2}")
                    item = f"__{formatted_numbers}_{speaker}_{time1}_to_{time2}"
                    #print(item)
                    if speaker == "Salesperson":
                        speaker = "left"
                    else:
                        speaker = "right"
                    #print(f"_{line_number}_{speaker}_{time1}_to_{time2}")
                    command1 = f"{document_name}" + speaker
                    command1_fix=file_lookup(command1+ '.wav',NameMatch)
                    #print(command1_fix)
                    command2 = f"{document_name}" + item
                    #print(os.listdir(directory_path))
                    
                    if None not in (wav_split_path, command1_fix, result_path, command2, time3, time4):
                        in_wav = (wav_split_path / command1_fix)
                        out_wav = (result_path / f"{command2}.wav")
                        cmd = [SOX_BIN, str(in_wav), str(out_wav), "trim", str(time3), f"={time4}"]
                        last_result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        sox_runs += 1
                        if last_result.returncode != 0:
                            sox_failures += 1
                            print(f"[WARN] sox failed (code={last_result.returncode}) for: {' '.join(cmd)}\n{(last_result.stderr or '')[:300]}")
                    else:
                        if not line_written:
                            line_written = True
                            
                            
# Summary of sox runs
if sox_runs == 0:
    print("[WARN] No sox commands were executed (no matching segments or missing wav files).")
else:
    print(f"[INFO] sox runs: {sox_runs}, failures: {sox_failures}")
    if last_result is not None and last_result.returncode == 0 and last_result.stdout:
        print(last_result.stdout)

# Record the end time
end_time = time.time()
end_datetime = datetime.fromtimestamp(end_time)
#print(start_datetime)
#print(end_datetime)

elapsed_datetime = end_datetime - start_datetime
#print(f"Step4_wav_cut total running time: {elapsed_datetime} seconds")         