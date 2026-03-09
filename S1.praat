form Test command line calls
    real Pitch_time_step_(s) 0.0
    sentence first_text .\mytest.wav
    sentence second_text .\mytest_result.txt
endform

pitchts = 'Pitch_time_step'


Read from file: first_text$
intens = Get intensity (dB)
writeFileLine: second_text$, intens, ",Nan,Nan"
To Pitch: pitchts, 65, 250
Down to PitchTier
mn = Get mean (curve): 0, 0
st = Get standard deviation (points): 0, 0
writeInfo: intens
appendInfo: ","
appendInfo: mn
appendInfo: ","
appendInfo: st
writeFileLine: second_text$, intens, "," ,mn, "," , st

#Save as text file: "C:\Users\mytest\Desktop\test\mytest1.txt"





