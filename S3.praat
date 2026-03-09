#Pitch and Shimmer Measures

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

# extract pitch related parameters
  select Pitch 'name$'
  pitch_min = Get quantile... 0 0 0.05 Hertz
  pitch_max = Get quantile... 0 0 0.95 Hertz
  pitch_mean = Get mean... 0 0 Hertz
  pitch_sd = Get standard deviation... 0 0 Hertz
  pitch_qup = Get quantile... 0 0 0.75 Hertz
  pitch_qdown = Get quantile... 0 0 0.25 Hertz

  # extract jitter parameters: time range (0 0 = all), shortest period, longest period, maximum period factor
  select PointProcess 'name$'
  jitter_local = Get jitter (local)... 0 0 0.0001 0.02 1.3
  jitter_local_abs =  Get jitter (local, absolute)... 0 0 0.0001 0.02 1.3
  jitter_rap = Get jitter (rap)... 0 0 0.0001 0.02 1.3
  jitter_ppq5 = Get jitter (ppq5)... 0 0 0.0001 0.02 1.3
  jitter_ddp = Get jitter (ddp)... 0 0 0.0001 0.02 1.3

#create output file and write the first line
#outputPath$ = "C:\Users\mytest\Desktop\pitch_and_jitter.csv"

appendInfo: "'outputPath$'", "call_id, Min Pitch, Max Pitch, Mean Pitch, SD Pitch, QUP Pitch, QDown Pitch, Jitter Local, Jitter Local ABS, Jitter Rap, Jitter PPQ5, Jitter DDP"
#save to a spreadsheet
writeFileLine: "'outputPath$'",
		...current_file$, ",",
		...pitch_min, ",",
                ...pitch_max, ",",
		...pitch_mean, ",",
		...pitch_sd, ",",
                ...pitch_qup, ",",
                ...pitch_qdown, ",",
		...jitter_local, ",",
                ...jitter_local_abs, ",",
		...jitter_rap, ",",
		...jitter_ppq5, ",",
                ...jitter_ddp

#endfor