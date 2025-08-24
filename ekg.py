import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque

# ----------------------
# Konfigurasi Serial
# ----------------------
port = 'COM5'        # Ganti dengan port Arduino kamu (cek di Device Manager)
baudrate = 9600

try:
    ser = serial.Serial(port, baudrate)
    print(f"Terhubung ke {port} dengan baudrate {baudrate}")
except Exception as e:
    print("Gagal membuka port serial:", e)
    exit()

# ----------------------
# Pengaturan Grafik
# ----------------------
maxLen = 250  # Jumlah titik ditampilkan (sekitar 10 detik @25Hz)
data = deque([0]*maxLen, maxlen=maxLen)

fig, ax = plt.subplots()
line, = ax.plot(data)
line.set_ydata(list(data))  # Inisialisasi awal agar tidak error

ax.set_ylim(0, 1023)              # Nilai analog dari AD8232
ax.set_title("Monitor Detak Jantung - AD8232")
ax.set_xlabel("Waktu")
ax.set_ylabel("Amplitudo (analogRead)")
# ax.invert_yaxis()              # Jangan aktifkan ini kalau ingin 0 di bawah

# ----------------------
# Filter Moving Average
# ----------------------
def moving_average(signal_list, window_size=5):
    if len(signal_list) < window_size:
        return signal_list[-1]
    return sum(list(signal_list)[-window_size:]) // window_size

# ----------------------
# Fungsi Update Grafik
# ----------------------
def update(frame):
    global data
    try:
        value = ser.readline().decode('utf-8').strip()
        if value.isdigit():
            raw = int(value)
            data.append(raw)  # Masukkan data mentah terlebih dahulu
            filtered = moving_average(data, window_size=5)
            line.set_ydata(list(data))  # Tampilkan sinyal yang sudah difilter
            print("Data masuk:", raw)   # Debug: pastikan data masuk
    except Exception as e:
        print("Error saat pembacaan:", e)
    return line,

# ----------------------
# Jalankan Animasi
# ----------------------
ani = animation.FuncAnimation(fig, update, interval=40)  # 25Hz
plt.tight_layout()
plt.show()
