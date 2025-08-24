import serial
import sys
import csv
import time
from collections import deque
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

# ----------------------
# Konfigurasi Serial
# ----------------------
port = 'COM5'
baudrate = 9600

try:
    ser = serial.Serial(port, baudrate, timeout=1)
    print(f"✅ Terhubung ke {port} dengan baudrate {baudrate}")
except Exception as e:
    print("❌ Gagal membuka port serial:", e)
    sys.exit()

# ----------------------
# File CSV untuk data EKG dan BPM
# ----------------------
ekg_file = open("dataset_ekg.csv", mode='w', newline='')
ekg_writer = csv.writer(ekg_file)
ekg_writer.writerow(["timestamp", "raw", "ema", "diff", "label"])

bpm_file = open("bpm_log.csv", mode='w', newline='')
bpm_writer = csv.writer(bpm_file)
bpm_writer.writerow(["timestamp", "bpm"])

# ----------------------
# Filter EMA
# ----------------------
alpha = 0.1
prev_ema = 512

def exponential_moving_average(new_value):
    global prev_ema
    ema = (alpha * new_value) + (1 - alpha) * prev_ema
    prev_ema = ema
    return int(ema)

# ----------------------
# PyQt5 GUI Application
# ----------------------
class BPMMonitor(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Real-Time EKG & BPM Monitor - AD8232")
        self.setGeometry(100, 100, 1000, 600)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.control_layout = QtWidgets.QHBoxLayout()

        # Grafik Raw EKG
        self.ekg_plot = pg.PlotWidget(title="Sinyal Detak Jantung (Raw)")
        self.ekg_plot.setYRange(0, 1023)
        self.ekg_curve = self.ekg_plot.plot(pen='y')
        self.ekg_data = deque([0]*500, maxlen=500)

        # Grafik BPM
        self.bpm_plot = pg.PlotWidget(title="Grafik Detak Jantung (BPM)")
        self.bpm_plot.setYRange(40, 160)
        self.bpm_curve = self.bpm_plot.plot(pen='g')
        self.bpm_data = deque([0]*120, maxlen=120)

        # Tombol kontrol
        self.start_button = QtWidgets.QPushButton("▶️ Start")
        self.stop_button = QtWidgets.QPushButton("⏹️ Stop")
        self.start_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)

        # Target BPM
        self.target_input = QtWidgets.QSpinBox()
        self.target_input.setRange(40, 180)
        self.target_input.setValue(75)
        self.target_input.setPrefix("Target: ")

        # Tambahkan ke layout
        self.control_layout.addWidget(self.start_button)
        self.control_layout.addWidget(self.stop_button)
        self.control_layout.addWidget(self.target_input)
        self.layout.addLayout(self.control_layout)
        self.layout.addWidget(self.ekg_plot)
        self.layout.addWidget(self.bpm_plot)

        self.is_recording = False
        self.threshold = 20
        self.beat_count = 0
        self.start_bpm_time = time.time()

        # Timer update data
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(5)  # Lebih cepat untuk raw signal

    def start_recording(self):
        self.is_recording = True
        print("▶️  Perekaman dimulai...")
        self.start_bpm_time = time.time()
        self.beat_count = 0

    def stop_recording(self):
        self.is_recording = False
        print("⏹️  Perekaman dihentikan.")

    def update_data(self):
        try:
            while ser.in_waiting:
                line = ser.readline().decode('utf-8').strip()
                if line.isdigit():
                    raw = int(line)
                    ema = exponential_moving_average(raw)
                    diff = raw - ema
                    timestamp = time.time()

                    # Update grafik EKG mentah
                    self.ekg_data.append(raw)
                    self.ekg_curve.setData(list(self.ekg_data))

                    if self.is_recording:
                        ekg_writer.writerow([timestamp, raw, ema, diff, 0])

                        if raw > ema + self.threshold:
                            self.beat_count += 1

                        elapsed = timestamp - self.start_bpm_time
                        if elapsed >= 1:
                            bpm = int((self.beat_count / elapsed) * 60)
                            bpm_writer.writerow([timestamp, bpm])
                            print(f"🫀 {bpm} BPM  | 🎯 Target: {self.target_input.value()}")

                            self.bpm_data.append(bpm)
                            self.bpm_curve.setData(list(self.bpm_data))

                            self.beat_count = 0
                            self.start_bpm_time = timestamp
        except Exception as e:
            print("❗ Error:", e)

    def closeEvent(self, event):
        try:
            bpm_file.close()
            ekg_file.close()
            ser.close()
            print("✅ File dan serial port ditutup dengan aman.")
        except:
            pass
        event.accept()

# ----------------------
# Jalankan Aplikasi
# ----------------------
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = BPMMonitor()
    window.show()
    sys.exit(app.exec_())
