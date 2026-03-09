#Jitter, Shimmer, HNR

form Read all files of the given type from the given directory
sentence current_file .\audios\mytest.wav
sentence outputPath .\audios\mytest.csv
endform

#Create Strings as file list... list 'source_directory$'
#file_count = Get number of strings
#for i from 1 to file_count
#select Strings list
#current_file$ = Get string... i
Read from file: current_file$
name$ = selected$ ("Sound")


To Intensity... 100 0
select Intensity 'name$'
start = 0
end = 10
min_int = Get minimum... start
... end Parabolic
max_int = Get maximum... start
... end parabolic
mean_int = Get mean... start end
... energy
range_of_int = max_int-min_int
select Intensity 'name$'
Remove

select Sound 'name$'
minimum_pitch = 70
maximum_pitch = 500

pitch_silence_threshold = 0.03
pitch_voicing_threshold = 0.45
pitch_octave_cost = 0.01
pitch_octave_jump_cost = 0.35
pitch_voiced_unvoiced_cost = 0.14

To Pitch (cc)... 0 minimum_pitch 15 no pitch_silence_threshold pitch_voicing_threshold 0.01 0.35 0.14 maximum_pitch

plus Pitch 'name$'

To PointProcess
points = Get number of points

select Sound 'name$'
plus Pitch 'name$'
plus PointProcess 'name$'
start = 0
end = 10
maximum_period_factor = 1.3
maximum_amplitude_factor = 1.6
#Voice report... start end minimum_pitch maximum_pitch maximum_period_factor maximum_amplitude_factor 0.03 0.45
report$ = Voice report... start end minimum_pitch maximum_pitch maximum_period_factor maximum_amplitude_factor 0.03 0.45

meanPitch = extractNumber (report$, "Mean pitch: ")
minPitch = extractNumber (report$, "Minimum pitch: ")
maxPitch = extractNumber (report$, "Maximum pitch: ")
pitch_range = maxPitch-minPitch

jitter_loc = extractNumber (report$, "Jitter (local): ") * 100
shimmer_loc = extractNumber (report$, "Shimmer (local): ") *100
mean_nhr = extractNumber (report$, "Mean noise-to-harmonics ratio: ")

#create output file and write the first line
#outputPath$ = "C:\Users\mytest\Desktop\jitter_shimmer_HNR.csv"

appendInfo: "'outputPath$'", "call_id, jitter_loc, shimmer_loc, HNR"
#save to a spreadsheet
writeFileLine: "'outputPath$'",
		...current_file$, ",",
		...jitter_loc, ",",
                ...shimmer_loc, ",",
                ...mean_nhr

#endfor