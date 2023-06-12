# AudioSlicer (Editor) for [ai-voice-cloning by mrq](https://git.ecker.tech/mrq/ai-voice-cloning/wiki/Training)

## Requirements (just use the same venv as for the ui)

- ffmpeg (ffprobe)
- PyQt6
- ffprobe-python

Clone this repo to "modules".
To install the requirements, activate your venv (`venv\Scripts\activate` on Windows) and run `pip install ffmpeg-python PyQt6 ffprobe-python`.

## Usage

Run main.py (with the activated venv)

Select either a generated audio_list.json (by this tool to continue working on the same project) or a generated whisper.json (by the ui with whisperx) in the traning folder of the voice.

Note: It is adviced to give a -1s trim offset for the start, whisperx cuts often to late, and you can cut it later with this tool.


## Buttons

- prev / next (alt+left / alt+right): go to the previous / next audio file
- delete (alt+down): delete the current audio file (not really delete but flag as not to export for training)
- play (alt+up) palys the segment
- trim (alt+t): trim the current audio file (respecting the 2 fields above, cuts x seconds from start/end - floats are allowed), after cutting, the length can be longer since ffprobe reports the actual length and not the weird whisper timestamps
- trim_undo: undos the previous trim: ONLY WORKS ONE TIME (could be improved)
- ffprobe returns the actual new length
- save (ctrl+s): save the current progress to audio_list.json 
- export: writes the train.txt and vaidation.txt (2% of the "good" samples taken)

## Notes

- To add new audio files, just transcribe them via the UI and then select the `audio_list.json`, it will add the new files to the list (takes a bit) DONT SELECT THE WHISPER.JSON AGAIN, IT WILL OVERWRITE THE WHOLE LIST, AND THEREFORE YOUR PROGESS. Also make sure to check the `skip existing` in the webui, otherwise the trimmed audio files will be overwritten, and the trim is gone.
- First import will be slow (or adding new files) - each file will be probed by ffmpeg for the real length
- The word quality is taken from whisperX, therefore its only an indicator nothing more.
- Every sentence including `...` is auto-excluded from traning (can be changed again - but thats why the progressbars aren't at 0 from the beginning and the "good/deleted segments" bar wont represent the actual outcome until a good amount of segments are flagged
- After hearing a segement, it gets auto flagged as "okey" and therefore marked as good to train

![image](https://github.com/Dschogo/audioslicer/blob/master/image.png?raw=true)


## Todo / Improvements

Waveform preview with two handles to trim visually - idk how yet
