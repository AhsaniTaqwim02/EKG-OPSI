import serial
import sys
import csv
import time
import threading
import keyboard
import os
from collections import deque
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

# ----------------------
# Konfigurasi Serial
# ----------------------
port = 'COM5'  # Ganti sesuai port kamu
baudrate = 9600

try:
    ser = serial.Serial(port, baudrate, timeout=1)
    print(f"✅ Terhubung ke {port} dengan baudrate {baudrate}")
except Exception as e:
    print("❌ Gagal membuka port serial:", e)
    sys.exit()

# ----------------------
# File CSV untuk data EKG mentah
# ----------------------
ekg_file = open("dataset_ekg.csv", mode='w', newline='')
ekg_writer = csv.writer(ekg_file)
ekg_writer.writerow(["timestamp", "raw", "ema", "diff", "label"])

# ----------------------
# File CSV untuk data BPM
# ----------------------
bpm_file = open("bpm_log.csv", mode='w', newline='')
bpm_writer = csv.writer(bpm_file)
bpm_writer.writerow(["timestamp", "bpm"])

# ----------------------
# EMA Filter
# ----------------------
alpha = 0.1
prev_ema = 512

def exponential_moving_average(new_value):
    global prev_ema
    ema = (alpha * new_value) + (1 - alpha) * prev_ema
    prev_ema = ema
    return int(ema)

# ----------------------
# Keyboard Listener
# ----------------------
is_recording = False

def monitor_keyboard():
    global is_recording
    while True:
        if keyboard.is_pressed('y') and not is_recording:
            is_recording = True
            print("▶️  Perekaman dimulai...\n")
            time.sleep(1)
        elif keyboard.is_pressed('s') and is_recording:
            is_recording = False
            print("⏹️  Perekaman dihentikan.\n")
            time.sleep(1)

threading.Thread(target=monitor_keyboard, daemon=True).start()

# ----------------------
# PyQtGraph Setup
# ----------------------
app = QtWidgets.QApplication([])
win = pg.GraphicsLayoutWidget()
win.setWindowTitle("Real-Time EKG Monitor - AD8232")
win.resize(1000, 400)
win.show()

plot = win.addPlot(title="Sinyal Detak Jantung (analogRead)")
curve = plot.plot(pen='g')
plot.setYRange(0, 1023)

maxLen = 500
data = deque([0] * maxLen, maxlen=maxLen)

# ----------------------
# BPM Detection
# ----------------------
threshold = 20
beat_count = 0
start_bpm_time = time.time()

def update():
    global beat_count, start_bpm_time
    try:
        if ser.in_waiting:
            line = ser.readline().decode('utf-8').strip()
            if line.isdigit():
                raw = int(line)
                ema = exponential_moving_average(raw)
                diff = raw - ema
                timestamp = time.time()

                # Simpan data EKG mentah
                if is_recording:
                    ekg_writer.writerow([timestamp, raw, ema, diff, 0])
                    
                    # Hitung detak
                    if raw > ema + threshold:
                        beat_count += 1

                    # Hitung dan simpan BPM setiap 5 detik
                    elapsed = timestamp - start_bpm_time
                    if elapsed >= 5:
                        bpm = int((beat_count / elapsed) * 60)
                        bpm_writer.writerow([timestamp, bpm])
                        print(f"🫀 {bpm} BPM  | Raw: {raw} | EMA: {ema} | Diff: {diff}")
                        beat_count = 0
                        start_bpm_time = timestamp

                # Update grafik
                data.append(raw)
                curve.setData(list(data))

    except Exception as e:
        print("❗ Error:", e)

# ----------------------
# Timer PyQt
# ----------------------
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(5)

# ----------------------
# Jalankan GUI
# ----------------------
QtWidgets.QApplication.instance().exec_()

# ----------------------
# Tutup file saat keluar
# ----------------------
ekg_file.close()
bpm_file.close()
ser.close()
