#Intensity and Shimmer Measures

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

  # calculate intensity related measures
  To Intensity... 100 0
  select Intensity 'name$'
  int_mean = Get mean... 0 0 energy
  int_sd = Get standard deviation... 0 0
  int_min = Get minimum... 0 0 Parabolic
  int_max = Get maximum... 0 0 Parabolic
  int_05 = Get quantile... 0 0 0.05
  int_95 = Get quantile... 0 0 0.95
  select Intensity 'name$'
  Remove

  # select PointProcess and sound to extract shimmer
  # parameters: time range (0 0 = all), shortest period, longest period, max period factor, max amplitude factor


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
  plus PointProcess 'name$'
  shimmer_local = Get shimmer (local)... 0 0 0.0001 0.02 1.3 1.6
  shimmer_local_dB = Get shimmer (local_dB)... 0 0 0.0001 0.02 1.3 1.6
  shimmer_apq3 = Get shimmer (apq3)... 0 0 0.0001 0.02 1.3 1.6
  shimmer_apq5 = Get shimmer (apq5)... 0 0 0.0001 0.02 1.3 1.6
  shimmer_apq11 =  Get shimmer (apq11)... 0 0 0.0001 0.02 1.3 1.6
  shimmer_dda = Get shimmer (dda)... 0 0 0.0001 0.02 1.3 1.6


appendInfo: "'outputPath$'", "call_id, Mean Intensity, Intensity SD, Min Intensity, Max Intensity, 05 Intensity, 95 Intensity, Shimmer Local, Shimmer Local dB, Shimmer APQ3, Shimmer APQ5, Shimmer APQ11, Shimmer DDA"
#save to a spreadsheet
writeFileLine: "'outputPath$'",
		...current_file$, ",",
		...int_mean, ",",
                ...int_sd, ",",
		...int_min, ",",
		...int_max, ",",
                ...int_05, ",",
                ...int_95, ",",
		...shimmer_local, ",",
                ...shimmer_local_dB, ",",
		...shimmer_apq3, ",",
		...shimmer_apq5, ",",
                ...shimmer_apq11, ",",
                ...shimmer_dda

#endfor