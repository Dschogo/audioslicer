import sys
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QToolTip, QFileDialog
import json
from PyQt6.uic import loadUi
from PyQt6 import QtGui
from PyQt6.QtCore import QModelIndex
import pathlib
import math
import threading
import winsound
import os
import tqdm
import time
import ffmpeg
import shutil
import ffprobe

from main_window import Ui_MainWindow

class StoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self,  *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

class MainWindow(QWidget, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.bt_next.clicked.connect(self.next)
        self.bt_prev.clicked.connect(self.prev)
        self.bt_save.clicked.connect(self.save)
        self.bt_play.clicked.connect(self.play_audio)
        self.bt_del.clicked.connect(self.delete)
        self.bt_trim.clicked.connect(self.trim_audio)
        self.bt_trim_2.clicked.connect(self.trim_restore)
        self.bt_export.clicked.connect(self.export)
        self.audio_list = {"audio": []}
        self.selected_row = 0
        self.music_thread = None

        def iter_load(resume=False):

            def already_parsed(aud):
                for seg in self.audio_list["audio"]:
                    if aud == seg['audio']:
                        return True
                return False

            try:

                with open(self.voice_path + "whisper.json", "r" , encoding="utf-8") as f:
                    whisp_f = json.load(f)
                    for file in tqdm.tqdm(whisp_f, position=0, leave=True):
                        for seg in tqdm.tqdm(whisp_f[file]["segments"], position=1, leave=False):
                            aud = file.replace(".wav", f"_{seg['id']:05d}.wav")
                            # id has 5 digits
                            if resume and already_parsed(aud):
                                continue
                            self.audio_list["audio"].append({
                                "audio": aud,
                                "text": seg["text"].strip(),
                                "words": seg["words"],
                                "length": math.floor((seg["end"] - seg["start"]) * 100) / 100,
                                "status": 2 if "..." in seg["text"] else -1
                            })
            except Exception as e:
                print(f"Error loading whisper.json {e}") 

        # name train.txt or 
        file = QFileDialog.getOpenFileName(self, 'Open file', str(pathlib.Path().resolve()) + "/training", "JSON files (*.json)")
        if file[0].endswith("audio_list.json"):
            with open(file[0], "r", encoding="utf-8") as f:
                self.audio_list = json.load(f)
                self.voice_path = file[0].replace("audio_list.json", "")
                iter_load(True)
                          
        else:
            self.voice_path = file[0].replace("whisper.json", "")
            
            try:
                iter_load()
                                        
            except Exception as e:
                print(f"Error loading whisper.json {e}")
                                    
                # disable qually table
                self.table_qualli.setEnabled(False)
                self.table_qualli.setHidden(True)

        # dump json 
        with open(f"{self.voice_path}audio_list.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(self.audio_list, indent=4, ensure_ascii=False))
    
        # create column view model#
        self.model = QtGui.QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Audio", "Text"])
        # add rows
        for audio in self.audio_list["audio"]:
            self.model.appendRow([
                QtGui.QStandardItem(audio["audio"]),
                QtGui.QStandardItem(str(audio["length"])),
                QtGui.QStandardItem(audio["text"]),
            ])

        if file[0].endswith("audio_list.json"):
            # recover all status colors
            for i in tqdm.tqdm(range(len(self.audio_list["audio"])), position=0, leave=True):
                self.update_color(i)
                
        
        # add model to table view, on click event
        self.tableView.setModel(self.model)
        self.tableView.clicked.connect(self.select_row_event)
        # set table view column width
        self.tableView.setColumnWidth(1, 30)

        
        self.trim_s.setValidator(QtGui.QDoubleValidator().setRange(0.0, 10.0))
        self.trim_e.setValidator(QtGui.QDoubleValidator().setRange(0.0, 10.0))

        # on text edit change event
        self.txt_edit.textChanged.connect(self.update_text)

        
        self.select_row(0)

        # register shortcuts
        self.bt_next.setShortcut("Alt+Right")
        self.bt_prev.setShortcut("Alt+Left")
        self.bt_play.setShortcut("Alt+Up")
        self.bt_save.setShortcut("Ctrl+S")
        self.bt_del.setShortcut("Alt+Down")
        self.bt_trim.setShortcut("Ctrl+T")

        # set focus to text edit
        self.txt_edit.setFocus()
        self.tableView.setStyleSheet("QTableView::item:selected { background-color: #0077c2; }")   

        # reset trim
        self.trim_s.setText("0.0")
        self.trim_e.setText("0.0")


    def play_audio(self):

        # play audio non ui blocking
        try:
            filename = f'''{self.voice_path}audio/{self.audio_list['audio'][self.selected_row]['audio']}'''
            winsound.PlaySound(filename, winsound.SND_ASYNC)
        except Exception as e:
            print(f"Error playing audio {e}")
        
        # set status to 0
        if self.audio_list["audio"][self.selected_row]["status"] == -1:
            self.audio_list["audio"][self.selected_row]["status"] = 0


    def trim_restore(self):
        filename = f'''{self.voice_path}audio/{self.audio_list['audio'][self.selected_row]['audio']}'''
        filename_copy = f'''{self.voice_path}audio_before_trim/{self.audio_list['audio'][self.selected_row]['audio']}.wav'''

        shutil.copyfile(filename_copy, filename)

        # get audio length
        if "length_org" in self.audio_list["audio"][self.selected_row]:
            self.audio_list["audio"][self.selected_row]["length"] = self.audio_list["audio"][self.selected_row]["length_org"]
        # update table
        self.model.setItem(self.selected_row, 1, QtGui.QStandardItem(str(self.audio_list["audio"][self.selected_row]["length"])))

        # set status
        self.set_status("trim_restore")
        self.play_audio()

    def trim_audio(self):
        # trim audio
        try:
            filename = f'''{self.voice_path}audio/{self.audio_list['audio'][self.selected_row]['audio']}'''
            start = float(self.trim_s.text())
            endd = float(self.trim_e.text())

            # get length of  audio via ffprobe
            
            length = float(ffprobe.FFProbe(f'''{self.voice_path}audio/{self.audio_list['audio'][self.selected_row]['audio']}''').audio[0].duration)

            end = length - endd
            
            # check if start is bigger than end
            if start > end:
                print("start is bigger than end")
                self.set_status("start > end")
                return
           
            if start == 0.0 and end == 0.0:
                print("start and end are 0")
                self.set_status("start and end are 0")
                return
            
            filename_copy = f'''{self.voice_path}audio_before_trim/{self.audio_list['audio'][self.selected_row]['audio']}.wav'''

            # copy audio to backup
            if not os.path.exists(f'''{self.voice_path}audio_before_trim'''):
                os.makedirs(f'''{self.voice_path}audio_before_trim''')
            shutil.copyfile(filename, filename_copy)

            #convert to samples
            sample_rate = 22050
            start_s = math.floor(start * sample_rate)
            end_s = math.floor(end * sample_rate)

            # trim using ffmpeg
            (ffmpeg
                .input(filename_copy)
                .filter('atrim', start_sample=start_s, end_sample=end_s)
                .filter('asetpts', 'PTS-STARTPTS') #reset timestamps
                .output(f'''{self.voice_path}audio/{self.audio_list['audio'][self.selected_row]['audio']}''')
                .global_args('-loglevel', 'quiet')
                .overwrite_output()
                .run()
            )

            # update audio length
            self.audio_list["audio"][self.selected_row]["length_org"] = length
            self.audio_list["audio"][self.selected_row]["length"] = math.floor((end - start) * 100) / 100
            # update table
            self.model.setItem(self.selected_row, 1, QtGui.QStandardItem(str(self.audio_list["audio"][self.selected_row]["length"])))
            # reset trim values
            self.trim_s.setText("0.0")
            self.trim_e.setText("0.0")
            self.play_audio()
            self.set_status("Trimmed audio")

        except Exception as e:
            print(f"Error trimming audio {e}")


    def select_row_event(self, row: QModelIndex):
        self.update_color(self.selected_row)
        self.selected_row = row.row()
        self.select_row(self.selected_row)


    def select_row(self, row: int):
        self.txt_edit.setText(self.audio_list["audio"][row]["text"])
        self.tableView.selectRow(self.selected_row)
        # update qually table
        self.model_qualli = QtGui.QStandardItemModel()
        self.model_qualli.setHorizontalHeaderLabels(["Word", "Qually"])
        # add rows
        #print(self.audio_list["audio"][row]["words"])
        for word in self.audio_list["audio"][row]["words"]:
            self.model_qualli.appendRow([
                QtGui.QStandardItem(word["word"]),
                QtGui.QStandardItem(str(word["score"]) if "score" in word else ""),
            ])
            # color row based on score
            if "score" in word:
                # gradient from red to green
                col = QtGui.QColor(int(255 - 255 * word["score"]), int(word["score"]*255), 0)

                # color selected row
                for i in range(self.model_qualli.columnCount()):
                    self.model_qualli.item(self.model_qualli.rowCount() - 1, i).setBackground(col)
        
        # add model to table view, on click event
        self.table_qualli.setModel(self.model_qualli)

        # reset trim values
        self.trim_s.setText("0.0")
        self.trim_e.setText("0.0")

        self.txt_edit.setFocus()
        
        self.update_progress()
        self.play_audio()


    def update_color(self, row: int):
        if self.audio_list["audio"][row]["status"] == 0:
            col = QtGui.QColor(150, 255, 150)
        elif self.audio_list["audio"][row]["status"] == 1:
            col = QtGui.QColor(100, 255, 10)
        elif self.audio_list["audio"][row]["status"] == 2:    
            col = QtGui.QColor(255, 150, 150)
        else:
            col = QtGui.QColor(255, 255, 255)

        # color selected row
        for i in range(self.model.columnCount()):
            self.model.item(row, i).setBackground(col)

        self.tableView.setStyleSheet("QTableView::item:selected { background-color: #0077c2; }")

    def update_text(self):
        if self.selected_row is None:
            return

        if self.audio_list["audio"][self.selected_row]["text"] == self.txt_edit.text():
            return
        
        self.audio_list["audio"][self.selected_row]["text"] = self.txt_edit.text()

        # update saudiolist status
        self.audio_list["audio"][self.selected_row]["status"] = 1
        self.update_color(self.selected_row)

        # update table view
        self.model.item(self.selected_row, 2).setText(self.txt_edit.text())
        

    def next(self):
        self.update_color(self.selected_row)
        if self.selected_row < len(self.audio_list["audio"]) - 1:
            self.selected_row += 1
        self.select_row(self.selected_row)


    def prev(self):
        self.update_color(self.selected_row)
        if self.selected_row > 0:
            self.selected_row -= 1
        self.select_row(self.selected_row)

    def update_progress(self):
        self.good_count = [0, 0, 0.0]
        for i in range(len(self.audio_list["audio"])):
            if self.audio_list["audio"][i]["status"] != -1:
                self.good_count[0] += 1
            if self.audio_list["audio"][i]["status"] == 2:
                self.good_count[1] += 1
            if self.audio_list["audio"][i]["status"] == 0 or self.audio_list["audio"][i]["status"] == 1:
                self.good_count[2] += self.audio_list["audio"][i]["length"]

        # 0 = all changed, 1 = to delete/bad, 3= unsused

        # update progress bar
        self.progressBar.setFormat("%d / %d - %.02f %%" % (self.good_count[0], len(self.audio_list["audio"]), self.good_count[0] / len(self.audio_list["audio"]) * 100))
        self.progressBar.setValue(int(self.good_count[0] / len(self.audio_list["audio"]) * 100))
        # self.progressBar.setFormat("%.02f %%" % (value * 100))
        # self.progressBar.setValue(int(value * 100))
        self.set_status(str(round(self.good_count[2] / 3600, 2)) + "h")



        if self.good_count[0] > 0:
            self.progressBar_2.setFormat("%d / %d - %.02f %%" % ((self.good_count[0] - self.good_count[1]), self.good_count[0], (self.good_count[0] - self.good_count[1]) / self.good_count[0] * 100))
            self.progressBar_2.setValue(int((self.good_count[0] - self.good_count[1]) / self.good_count[0] * 100))
        else:
            self.progressBar_2.setValue(0)
            # all changed / to delete
            self.progressBar_2.setFormat("%d / %d - %.02f %%" % (0, 0, 0))

    def export(self):

        # get shortest 10% of audio
        shot_list = []
        for audio in self.audio_list["audio"]:
            if audio["status"] == 0 or audio["status"] == 1:
                shot_list.append([audio["audio"], audio["length"], audio["text"]])
        shot_list.sort(key=lambda x: x[1])
        shot_list = shot_list[:int(len(shot_list) * 0.02)]
        # rename old train.txt to train.txt.bak with timestamp
        os.rename(self.voice_path + "train.txt", self.voice_path + "train.txt.bak." + str(int(time.time())))

        # save validation file
        os.rename(self.voice_path + "validation.txt", self.voice_path + "validation.txt.bak." + str(int(time.time())))

        with open(self.voice_path + "validation.txt", "w", encoding="utf-8") as f:
            for shot in shot_list:
                f.write("audio/" + shot[0] + "|" + shot[2].strip() + "\n")


        
        with open(self.voice_path + "train.txt", "w", encoding="utf-8") as f:
            for audio in self.audio_list["audio"]:
                if audio["status"] == 0 or audio["status"] == 1:
                    # check if audio is not in shot list
                    if audio["audio"] not in [shot[0] for shot in shot_list]:
                        f.write("audio/" + audio["audio"] + "|" + audio["text"].strip() + "\n")
                # else:
                #     # move audio file to trash
                #     os.rename(self.voice_path + audio["audio"], self.voice_path + "trash/" + audio["audio"].split("/")[-1])

        self.set_status("Saved")

    def save(self):
        with open(self.voice_path + "audio_list.json", "w", encoding="utf-8") as f:
            json.dump(self.audio_list, f, indent=4, ensure_ascii=False)

        self.set_status("Saved")

    def delete(self):
        
        self.update_color(self.selected_row)
        if self.audio_list["audio"][self.selected_row]["status"] != 2:
            self.audio_list["audio"][self.selected_row]["status"] = 2
            self.tableView.setStyleSheet("QTableView::item:selected { background-color: #f61c0d; }")    
        else:
            self.audio_list["audio"][self.selected_row]["status"] = 1
            self.tableView.setStyleSheet("QTableView::item:selected { background-color: #0077c2; }")    

        
        
        

    def set_status(self, text):
        self.label.setText(text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())