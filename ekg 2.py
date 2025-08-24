import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque

# ----------------------
# Konfigurasi Serial
# ----------------------
port = 'COM5'        # Ganti dengan port Arduino kamu
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
maxLen = 250
data = deque([0]*maxLen, maxlen=maxLen)

fig, ax = plt.subplots()
line, = ax.plot(data)
line.set_ydata(list(data))

ax.set_ylim(0, 1023)
ax.set_title("Monitor Detak Jantung - AD8232 (Hybrid Filter)")
ax.set_xlabel("Waktu")
ax.set_ylabel("Amplitudo (analogRead)")

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
# Fungsi Update Grafik
# ----------------------
threshold = 40  # selisih lonjakan yang dianggap detak

def update(frame):
    global data
    try:
        value = ser.readline().decode('utf-8').strip()
        if value.isdigit():
            raw = int(value)
            ema = exponential_moving_average(raw)

            # Jika lonjakan (misal: lebih tinggi dari EMA + threshold)
            if raw > ema + threshold:
                output = raw  # tampilkan lonjakan mentah
            else:
                output = ema  # tampilkan hasil filter

            data.append(output)
            line.set_ydata(list(data))
            print(f"Raw: {raw}, EMA: {ema}, Output: {output}")

    except Exception as e:
        print("Error saat pembacaan:", e)
    return line,

# ----------------------
# Jalankan Animasi
# ----------------------
ani = animation.FuncAnimation(fig, update, interval=40)
plt.tight_layout()
plt.show()
