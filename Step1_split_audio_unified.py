import os
import shutil
import subprocess
import re
import platform
from pathlib import Path

# if platform.system() == "Windows":
#     sox_path = './tools/sox.exe'
# elif platform.system() == "Linux":
#     sox_path = 'sox'
# else:
#     sox_path = 'sox'


# BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT", Path(__file__).resolve().parent)).resolve()
BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT") or Path.cwd()).resolve()



if platform.system() == "Windows":
    sox_path = str(BASE_DIR / "tools" / "sox.exe")

elif platform.system() == "Linux":
    # Prefer bundled sox if you ship it
    bundled = BASE_DIR / "tools" / "sox"
    if bundled.exists():
        sox_path = str(bundled)
    else:
        # Fall back to system sox
        sox_path = shutil.which("sox") or "sox"

else:
    sox_path = shutil.which("sox") or "sox"


input_folder = BASE_DIR / "input"
output_folder = BASE_DIR / "output"

output_folder_mono = output_folder / "mono"
output_folder_stereo = output_folder / "stereo"
output_folder_convert = output_folder / "convert"
output_folder_split = output_folder / "split"

output_mono_folder = BASE_DIR / "output_mono"
output_mono_folder_split = output_mono_folder / "split"

for p in [
    input_folder,
    output_folder_mono,
    output_folder_stereo,
    output_folder_convert,
    output_folder_split,
    output_mono_folder_split,
]:
    p.mkdir(parents=True, exist_ok=True)



def replace_non_ascii_and_whitespace_with_underscore(input_folder):
    for root, _, files in os.walk(input_folder):
        for file in files:
            old_file_path = os.path.join(root, file)
            new_file_name = re.sub('[^\\x00-\\x7F]', '_', file)
            new_file_name = re.sub('\\s+', '_', new_file_name)
            new_file_name = re.sub('[&()\\\'"]', '_', new_file_name)
            # name, extension = new_file_name.rsplit('.', 1)
            # name, extension = os.path.splitext(new_file_name)
            # new_file_name = f"{name}.{extension.lower()}"
            name, extension = os.path.splitext(new_file_name)
            if extension:
                new_file_name = f"{name}{extension.lower()}"

            new_file_path = os.path.join(root, new_file_name)
            if new_file_name != file:
                os.rename(old_file_path, new_file_path)
                print(f'''Renamed: {file} -> {new_file_name}''')


def get_num_channels(file_path):
    result = subprocess.run([
        sox_path,
        '--i',
        file_path],
        capture_output = True,
        text = True)
    output = result.stdout.lower()
    match = re.search('channels\\s*:\\s*(\\d+)', output)
    if match:
        return int(match.group(1))


def convert_to_wav(input_file, output_folder):
    output_file = os.path.join(output_folder, os.path.splitext(os.path.basename(input_file))[0] + '.wav')
    print(f'''Converting {input_file} to {output_file}''')
    subprocess.run([
        sox_path,
        input_file,
        output_file])


def split_to_mono(input_file, output_folder):
    output_file_left = os.path.join(output_folder, f'''{os.path.splitext(os.path.basename(input_file))[0]}_left.wav''')
    output_file_right = os.path.join(output_folder, f'''{os.path.splitext(os.path.basename(input_file))[0]}_right.wav''')
    print(f'''Splitting {input_file} to {output_file_left}''')
    subprocess.run([
        sox_path,
        input_file,
        output_file_left,
        'remix',
        '1'])
    print(f'''Splitting {input_file} to {output_file_right}''')
    subprocess.run([
        sox_path,
        input_file,
        output_file_right,
        'remix',
        '2'])


def main():
    # input_folder = './input'
    # output_folder = './output'
    # output_folder_mono = './output/mono'
    # output_folder_stereo = './output/stereo'
    # output_folder_convert = './output/convert'
    # output_folder_split = './output/split'
    
    # output_mono_folder_split = './output_mono/split'
    # os.makedirs(output_folder, exist_ok=True)
    # os.makedirs(output_folder_mono, exist_ok=True)
    # os.makedirs(output_folder_stereo, exist_ok=True)
    # os.makedirs(output_folder_convert, exist_ok=True)
    # os.makedirs(output_folder_split, exist_ok=True)
    # os.makedirs(output_mono_folder_split, exist_ok=True)
    replace_non_ascii_and_whitespace_with_underscore(input_folder)
    for root, _, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith('.mp3') or file.lower().endswith('.wav'):
                input_file = os.path.join(root, file)
                num_channels = get_num_channels(input_file)
                if num_channels == 1:
                    print(f'''{file} is MONO''')
                    shutil.move(input_file, os.path.join(output_folder_mono, file))
                    if file.lower().endswith('.mp3'):
                        convert_to_wav(os.path.join(output_folder_mono, file), output_mono_folder_split)
                    if file.lower().endswith('.wav'):
                        shutil.copy2(os.path.join(output_folder_mono, file),os.path.join(output_mono_folder_split, file))
                    continue
                if num_channels == 2:
                    print(f'''{file} is STEREO''')
                    shutil.move(input_file, os.path.join(output_folder_stereo, file))
                    if file.lower().endswith('.mp3'):
                        convert_to_wav(os.path.join(output_folder_stereo, file), output_folder_convert)
                    if file.lower().endswith('.wav'):
                        shutil.copy2(os.path.join(output_folder_stereo, file),os.path.join(output_folder_convert, file))
                    split_to_mono(os.path.join(output_folder_convert, os.path.splitext(file)[0] + '.wav'), output_folder_split)
                    continue
                print(f'''{file} cannot be processed''')

if __name__ == '__main__':
    print('Fix illegal characters in files name and separate the left and right audio channels')
    print('Usage: put mp3 or wav files under ./input and run this program')
    main()
