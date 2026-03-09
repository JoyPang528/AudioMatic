import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

"""
The input are the pairs of json files
1, The outout are the txt file which is stored in a seperate directory, each pair of json file generate one txt document.
2, Generate a skipped_pairs txt file, some json files only have their left part or only have their light part
(the same with step 3).
3, Generate a crosstalk_pairs txt file, to show which audio file have crosstalk,
and (from the generated txt files) calculatethe percentage of the crosstalk existence.
"""

#print("Begin to run Step3_json_to_txt, json files to text files...")

# BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT", Path(__file__).resolve().parent)).resolve()
BASE_DIR = Path(os.environ.get("AUDIOMATIC_ROOT") or Path.cwd()).resolve()


OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

start_time = time.time()
start_datetime = datetime.fromtimestamp(start_time)

result_path = OUTPUT_DIR

# Specify the directory containing your JSON files
# directory_path = './output/output_json'
directory_path = OUTPUT_DIR / "output_json"

# Check if the directory is empty
if not os.path.exists(directory_path) or not os.listdir(directory_path):
    print(f"Error: The directory '{directory_path}' is empty or does not exist. Please ensure it contains files before proceeding.")
    sys.exit(1)  # Exit the program with an error code



# result_path = './output/output_txt'
result_path = OUTPUT_DIR / "output_txt"

# result_path_1 = './output/output_txt_1'
result_path_1 = OUTPUT_DIR / "output_txt_1"
# os.makedirs(result_path, exist_ok=True)
# os.makedirs(result_path_1, exist_ok=True)
result_path.mkdir(parents=True, exist_ok=True)
result_path_1.mkdir(parents=True, exist_ok=True)

# Initialize a count for generated files
file_count = 0
skipped_file_count = 0

# Initialize an empty dictionary to store pairs of documents
document_pairs = {}

# List to store names of skipped pairs
skipped_pairs = []

# List all files in the directory
all_files = os.listdir(directory_path)

# Iterate through all files in the directory
for file_name in all_files:
    # Split the file name into base and extension parts
    base_name, extension = os.path.splitext(file_name)

    # Check if the file is a "_right.json" or "_left.json" document
    if extension == ".json" and (base_name.endswith("_right") or base_name.endswith("_left")):
        mutual_base_name = base_name.rsplit('_', 1)[0]  # Extract the mutual part
        pair_key = mutual_base_name  # Use the mutual part as the key
        file_path = os.path.join(directory_path, file_name)
        # Add the file path to the appropriate pair key
        if pair_key not in document_pairs:
            document_pairs[pair_key] = {'_right': None, '_left': None}
        document_pairs[pair_key][f'_{base_name.split("_")[-1]}'] = file_path

# Now, document_pairs contains pairs of documents grouped by their mutual part
# Each pair is stored as a dictionary with '_right' and '_left' keys
crosstalk_test_results = []
crosstalk_pairs = []

# Process and generate results for each pair
for mutual_part, pair_info in document_pairs.items():
    right_document = pair_info['_right']
    left_document = pair_info['_left']

    # Check if the files exist
    if left_document is None:
        #print(f"Skipping pair '{mutual_part}', its '_left' file is missing.")
        skipped_pairs.append(f"Skipping pair '{mutual_part}', its '_left' file is missing.")
        skipped_file_count += 1
        continue
    if right_document is None:
        #print(f"Skipping pair '{mutual_part}', its '_right' file is missing.")
        skipped_pairs.append(f"Skipping pair '{mutual_part}', its '_right' file is missing.")
        skipped_file_count += 1
        continue

        

    # Load the content of the "_right.json" document
    with open(right_document, 'r', encoding='latin1') as right_file:
        right_data = json.load(right_file)
        
        if "word_segments" in right_data:
            del right_data["word_segments"]
            
    # Convert the modified dictionary back to a JSON string
    modified_json_str = json.dumps(right_data, indent=2)

    right = json.loads(modified_json_str)
    #print(right)
    
    
    
    # Load the content of the "_left.json" document
    with open(left_document, 'r', encoding='latin1') as left_file:
        left_data = json.load(left_file)
        if "word_segments" in left_data:
            del left_data["word_segments"]
            
    # Convert the modified dictionary back to a JSON string
    modified_json_str = json.dumps(left_data, indent=2)

    left = json.loads(modified_json_str)
    #print(left)
    
    # Create a new array to store extracted values, Customer contains the right_data
    Customer = []
    
    # Extract the "segement" array
    segments_right = right_data.get("segments", [])
    
    # Iterate through each dictionary in the "segments_left" array
    for segment in segments_right:
        # Access and append desired values to the new array
        Customer.append({
            "start": segment["start"],
            "text": segment["text"],
            "end": segment["end"],
            "words": segment.get("words", [])
        })
        
    # Create a new array to store extracted values, Salesperson contains the left_data
    Salesperson = []
    
    # Extract the "segement" array
    segments_left = left_data.get("segments", [])
    
    # Iterate through each dictionary in the array
    for segment in segments_left:
        Salesperson.append({
            "start": segment["start"],
            "text": segment["text"],
            "end": segment["end"],
            "words": segment.get("words", [])
        })
    
    
    # Create a merged array, merge the customer data and salesperson data together
    merged_array = []
    
    # Add dictionaries from Customer with source information
    for dictionary in Customer:
        merged_array.append({
            "data": dictionary,
            "source": "Customer"
        })
    
    # Add dictionaries from Salesperson with source information
    for dictionary in Salesperson:
        merged_array.append({
            "data": dictionary,
            "source": "Salesperson"
        })
    # Sort the merged array based on the "start" value within each dictionary
    sorted_merged_array = sorted(merged_array, key=lambda x: x["data"].get("start", ""))
      
    # Iterate through the data and update the "end" value
    for entry in sorted_merged_array:
        entry_data = entry["data"]
        words = entry_data.get("words", [])  # Get the "words" list, or an empty list if it's not present
        

    
        # Update the "start" value with the first "start" value from "words" if available
        if words:
            entry_data["start"] = words[0].get("start", entry_data["start"])
    
        # Update the "end" value with the last "end" value from "words" or the previous "end" value if the last "word" is missing an "end" value
        if words:
            last_end = words[-1].get("end")
            if last_end is not None:
                entry_data["end"] = last_end
            elif len(words) > 1:
                second_last_words = words[-2]
                if "end" in second_last_words:                    
                    entry_data["end"] = words[-2].get("end")


    # Delete the words part    
    for entry in sorted_merged_array:
        entry_data = entry["data"]
        if "words" in entry_data:
            del entry_data["words"]
    
    # Initialize variables
    result_data = []
    current_source = None
    merged_text = ""
    merged_start = None
    merged_end = None
    merged_counts = {}
    count_data = 1
    
    # Define a function to format the time value
    def format_time(time_value):
    
        minutes = int(time_value // 60)
        seconds = int(time_value % 60)
        #milliseconds = int((time_value % 1) * 1000)
        end_string = str(time_value)
        if len(end_string.split('.')[-1]) == 2:
            milliseconds = int(end_string.split('.')[-1] + "0")
            
        elif len(end_string.split('.')[-1]) == 1:
            milliseconds = int(end_string.split('.')[-1] + "00")
        else:
            milliseconds = int(end_string.split('.')[-1])
        
        return "[{:02}:{:02}:{:03}]".format(minutes, seconds, milliseconds)
    
    # Iterate through the data
    for item in sorted_merged_array:
        source = item["source"]
        text = item["data"].get("text", "")
        text = text.strip()
        start = item["data"].get("start", None)
        end = item["data"].get("end", None)
    
    
        # If the current source is the same as the previous one, merge "text" values
        if source == current_source:
            text = " " + text
            merged_text += text
            merged_end = end  # Update the end time for merging
            count_data += 1
            
        else:
            # Append the merged data if there's any
            if merged_text:
                # Format the start and end values
                merged_start_formatted = format_time(merged_start)
                merged_end_formatted = format_time(merged_end)
                result_data.append({"source": current_source, "start": merged_start_formatted, "end": merged_end_formatted, "text": merged_text, "count_data": count_data})
                if current_source in merged_counts:
                    merged_counts[current_source] += count_data
                else:
                    merged_counts[current_source] = count_data
            # Set the start and end values for the new source
            merged_text = text
            merged_start = start
            merged_end = end
            count_data = 1  # Reset count_data for the new source
    
        # Update the current source
        current_source = source
    
    # Append the last merged data
    if merged_text:
        # Format the start and end values for the last source
        merged_start_formatted = format_time(merged_start)
        merged_end_formatted = format_time(merged_end)
        result_data.append({"source": current_source, "start": merged_start_formatted, "end": merged_end_formatted, "text": merged_text, "count_data": count_data})
        if current_source in merged_counts:
            merged_counts[current_source] += count_data
        else:
            merged_counts[current_source] = count_data
        
        # Delete the first row, if it is not Salesperson
        if result_data and result_data[0]['source'] == 'Salesperson':
        
            result_data = result_data
        if result_data and result_data[0]['source'] == 'Customer':
            result_data.pop(0)

        
        # Iterate through the list, excluding the last element
        for i in range(len(result_data) - 1):
            current_end = result_data[i]['end']
            next_start = result_data[i + 1]['start']

            # Check if the 'end' value is greater than the 'start' value of the next element
            if current_end < next_start:
                crosstalk_test_results.append(True)
            else:
               crosstalk_test_results.append(False)
               #print(f"Skipping pair '{mutual_part}' exists crosstalk.")
               crosstalk_pairs.append(f"Skipping pair '{mutual_part}' exists crosstalk.")

    #print(result_data)
    if result_data:
        # Create the result file path using the mutual part and save it as a TXT file
        result_file_path = os.path.join(result_path, f"{mutual_part}_result.txt")
        
        with open(result_file_path, 'w', encoding='utf-8') as result_file:
            for item in result_data:
                result_file.write(f"{item['source']}: {item['start']} {item['text']} {item['end']}\n")
            file_count += 1
    #else:
     #   os.remove(result_file_path)
    
    # Create the result file path using the mutual part and save it as a TXT file

        result_file_path_1 = os.path.join(result_path_1, f"{mutual_part}__result.txt")
        with open(result_file_path_1, 'w', encoding='utf-8') as result_file:
            for item in result_data:
                result_file.write(f"{item['source']}: {item['start']} {item['text']} {item['end']} {item['count_data']}\n")
            file_count += 1
	    
	    

false_count = crosstalk_test_results.count(False)
total_count = len(crosstalk_test_results)
#print(total_count)

if len(crosstalk_test_results) == 0:
    print("there is no crosstalk")
else:
    # Calculate the percentage of crosstalk
    percentage_false = (false_count / total_count) * 100

    #print(f"From the generated txt files, the percentage of crosstalk is: '{percentage_false:.3f}'%.")
    crosstalk_pairs.append(f"From the generated txt files, the percentage of crosstalk is: '{percentage_false:.3f}'%.")

# Write the list of skipped pairs to a text file
skipped_filename = os.path.join(result_path, "skipped_pairs.txt")
with open(skipped_filename, 'w') as skipped_file:
    skipped_file.write("Skipped Pairs:\n")
        
    for pair in skipped_pairs:
        skipped_file.write(f"{pair}\n")
        
    skipped_file.write(f"\nProcessing completed. Skipped {skipped_file_count} files. Generated {file_count} output text files. Result documents are generated and stored in the results file of the directory.")
    
# Write the list of crosstalk pairs to a text file
crosstalk_filename = os.path.join(result_path, "crosstalk_pairs.txt")
with open(crosstalk_filename, 'w') as crosstalk_file:
    crosstalk_file.write("Skipped Pairs:\n")
        
    for pair in crosstalk_pairs:
        crosstalk_file.write(f"{pair}\n")

#print(f"\nProcessing completed. Skipped {skipped_file_count} files. Generated {file_count} output text files. Result documents are generated and stored in the results file of the directory.")
# Record the end time
end_time = time.time()
end_datetime = datetime.fromtimestamp(end_time)
#print(start_datetime)
#print(end_datetime)

elapsed_datetime = end_datetime - start_datetime
#rint(f"Step3_json_to_txt total running time: {elapsed_datetime} seconds")

