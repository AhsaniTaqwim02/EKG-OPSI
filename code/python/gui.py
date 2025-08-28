import sys
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import serial
import serial.tools.list_ports
import time
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import threading
import queue
import os
from scipy.signal import butter, filtfilt, iirnotch  # Tambahkan import untuk filter

# --- KONFIGURASI ---
SERIAL_PORT = None  # Akan diatur otomatis
BAUD_RATE = 9600
SAMPLING_RATE_HZ = 250
PLOT_WINDOW_SAMPLES = 10 * SAMPLING_RATE_HZ

BPM_THRESHOLD = 620
BPM_AVG_WINDOW = 15
THEME_NAME = "cyborg" # Tema gelap (pilihan lain: darkly, solar)

def detect_serial_port():
    """
    Deteksi otomatis port serial yang kemungkinan adalah Arduino.
    Mengembalikan nama port (misal: 'COM3') atau None jika tidak ditemukan.
    """
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        # Deteksi berdasarkan nama/manufaktur yang umum pada Arduino
        if ("Arduino" in port.description) or ("CH340" in port.description) or ("USB Serial" in port.description) or ("ttyACM" in port.device) or ("ttyUSB" in port.device):
            return port.device
    # Jika tidak ada yang cocok, kembalikan port pertama jika ada
    if ports:
        return ports[0].device
    return None

# =============================================================================
# JENDELA UTAMA APLIKASI GUI
# =============================================================================
class EkgApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Modern EKG Monitoring")
        self.is_started = False
        self.csv_file = None
        self.ser = None  # Serial object
        self.sampling_rate = SAMPLING_RATE_HZ
        self.plot_window_sec = 10  # window plot dalam detik
        self.buffer_maxlen = self.sampling_rate * self.plot_window_sec
        self.data_buffer = []  # list of tuple (t, signal, bpm)
        self.last_beat_time = 0
        self.beat_timestamps = []
        self.current_bpm = 0
        self.last_value = 0
        plt.style.use('dark_background')

        # Filter settings (pindahkan ke sini sebelum _create_widgets)
        self.filter_enabled = tk.BooleanVar(value=False)
        self.filtered_buffer = []  # buffer untuk hasil filter

        self._create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.csv_filename = None  # simpan nama file untuk ekspor pandas
        self.last_saved_filename = None
        self.last_subject_info = None

        # Tambahan untuk threading & queue
        self.serial_thread = None
        self.serial_queue = queue.Queue()
        self.serial_thread_stop = threading.Event()
        self.is_paused = False

    def _create_widgets(self):
        # Ganti pack dengan grid, gunakan sticky untuk dinamis
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=0)
        main_frame.columnconfigure(1, weight=1)

        # --- FRAME KIRI (KONTROL & METADATA) ---
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="ns", padx=(0, 15))
        left_frame.rowconfigure(2, weight=1)

        # Metadata Frame
        meta_frame = ttk.Labelframe(left_frame, text="Informasi Subjek", padding=15)
        meta_frame.grid(row=0, column=0, sticky="ew")
        meta_frame.columnconfigure(1, weight=1)
        
        ttk.Label(meta_frame, text="Label ID:").grid(row=0, column=0, sticky=W, pady=5)
        self.label_input = ttk.Entry(meta_frame, width=20)
        self.label_input.insert(0, "subjek_01")
        self.label_input.grid(row=0, column=1, sticky=W+E, pady=5)
        
        ttk.Label(meta_frame, text="Jenis Kelamin:").grid(row=1, column=0, sticky=W, pady=5)
        self.gender_var = tk.StringVar()
        self.gender_combo = ttk.Combobox(meta_frame, textvariable=self.gender_var, values=["Laki-laki", "Perempuan"], state="readonly")
        self.gender_combo.current(0)
        self.gender_combo.grid(row=1, column=1, sticky=W+E, pady=5)
        
        ttk.Label(meta_frame, text="Usia:").grid(row=2, column=0, sticky=W, pady=5)
        self.age_input = ttk.Entry(meta_frame, width=20)
        self.age_input.insert(0, "25")
        self.age_input.grid(row=2, column=1, sticky=W+E, pady=5)

        ttk.Label(meta_frame, text="Kondisi:").grid(row=3, column=0, sticky=W, pady=5)
        self.condition_var = tk.StringVar()
        self.condition_combo = ttk.Combobox(meta_frame, textvariable=self.condition_var, values=["Sehat", "Sakit", "Lainnya"], state="readonly")
        self.condition_combo.current(0)
        self.condition_combo.grid(row=3, column=1, sticky=W+E, pady=5)

        # Label untuk menampilkan subjek terakhir (pindah ke metadata frame)
        self.last_subject_label_var = tk.StringVar(value="Subjek terakhir: -")
        self.last_subject_label = ttk.Label(meta_frame, textvariable=self.last_subject_label_var, font=("Helvetica", 8), bootstyle="secondary")
        self.last_subject_label.grid(row=4, column=0, columnspan=2, sticky=W, pady=(10,0))

        # Control Frame
        control_frame = ttk.Labelframe(left_frame, text="Kontrol Perekaman", padding=15)
        control_frame.grid(row=1, column=0, sticky="ew", pady=20)
        control_frame.columnconfigure(0, weight=1)

        self.save_var = tk.BooleanVar(value=True)
        self.save_checkbox = ttk.Checkbutton(control_frame, text="Simpan Data ke CSV", variable=self.save_var, bootstyle="round-toggle")
        self.save_checkbox.grid(row=0, column=0, sticky="nsew", pady=10)

        self.start_button = ttk.Button(control_frame, text="Start", command=self.start_task, bootstyle="success")
        self.start_button.grid(row=1, column=0, sticky="nsew", pady=5)
        
        self.pause_button = ttk.Button(control_frame, text="Pause", command=self.pause_task, state=DISABLED)
        self.pause_button.grid(row=2, column=0, sticky="nsew", pady=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_task, state=DISABLED, bootstyle="danger")
        self.stop_button.grid(row=3, column=0, sticky="nsew", pady=5)

        # Tambah tombol Reset Plot
        self.reset_button = ttk.Button(control_frame, text="Reset Plot", command=self.reset_plot, bootstyle="warning")
        self.reset_button.grid(row=4, column=0, sticky="nsew", pady=5)

        # Tambahkan checkbox filter di bawah checkbox simpan data
        self.filter_checkbox = ttk.Checkbutton(
            control_frame, text="Aktifkan Filter Sinyal", variable=self.filter_enabled, bootstyle="round-toggle",
            command=self._on_filter_toggle
        )
        self.filter_checkbox.grid(row=5, column=0, sticky="nsew", pady=5)

        # BPM Display
        bpm_frame = ttk.Frame(left_frame)
        bpm_frame.grid(row=2, column=0, sticky="nsew")
        bpm_frame.rowconfigure(0, weight=1)
        bpm_frame.rowconfigure(1, weight=2)
        bpm_frame.rowconfigure(2, weight=1)
        bpm_frame.columnconfigure(0, weight=1)

        ttk.Label(bpm_frame, text="BPM", font=("Helvetica", 20), anchor="center", justify="center").grid(row=0, column=0, sticky="nsew", pady=(20,0))
        self.bpm_label_var = tk.StringVar(value="--")
        ttk.Label(
            bpm_frame,
            textvariable=self.bpm_label_var,
            font=("Helvetica", 72, "bold"),
            bootstyle="info",
            anchor="center",
            justify="center"
        ).grid(row=1, column=0, sticky="nsew")
        self.bpm_stats_var = tk.StringVar(value="Rata-rata: --   Maks: --   Min: --")
        self.bpm_stats_label = ttk.Label(
            bpm_frame,
            textvariable=self.bpm_stats_var,
            font=("Helvetica", 12),
            bootstyle="secondary",
            anchor="center",
            justify="center"
        )
        self.bpm_stats_label.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        # --- FRAME KANAN (PLOT) ---
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew")
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        right_frame.columnconfigure(1, weight=1)  # Tambah kolom untuk subplot filter

        self.fig = Figure(figsize=(14, 8), dpi=100)  # Lebarkan figure
        self.fig.patch.set_facecolor('#2a2a2a') # Warna background figure

        # Subplot kiri: original
        self.ax_signal = self.fig.add_subplot(221)
        self.ax_bpm = self.fig.add_subplot(223)
        # Subplot kanan: filtered
        self.ax_signal_filt = self.fig.add_subplot(222)
        self.ax_bpm_filt = self.fig.add_subplot(224)
        # sharex dihapus
        
        self.ax_signal.set_facecolor('#3a3a3a')
        self.ax_signal.set_title("Sinyal EKG", color='white')
        self.ax_signal.set_ylabel("Nilai ADC", color='white')
        self.ax_bpm.set_facecolor('#3a3a3a')
        self.ax_bpm.set_title("Denyut Jantung (BPM)", color='white')
        self.ax_bpm.set_ylabel("BPM", color='white')
        self.ax_bpm.set_xlabel("Waktu (detik)", color='white')
        
        # Set judul dan label subplot filter
        self.ax_signal_filt.set_facecolor('#3a3a3a')
        self.ax_signal_filt.set_title("Sinyal EKG (Filtered)", color='white')
        self.ax_signal_filt.set_ylabel("Nilai ADC", color='white')
        self.ax_bpm_filt.set_facecolor('#3a3a3a')
        self.ax_bpm_filt.set_title("Denyut Jantung (BPM, Filtered)", color='white')
        self.ax_bpm_filt.set_ylabel("BPM", color='white')
        self.ax_bpm_filt.set_xlabel("Waktu (detik)", color='white')

        for ax in [self.ax_signal, self.ax_bpm, self.ax_signal_filt, self.ax_bpm_filt]:
            ax.tick_params(axis='x', colors='white')
            ax.tick_params(axis='y', colors='white')
            ax.spines['bottom'].set_color('white')
            ax.spines['top'].set_color('white') 
            ax.spines['right'].set_color('white')
            ax.spines['left'].set_color('white')

        self.line_signal, = self.ax_signal.plot([], [], color='cyan', lw=1.5)
        self.line_bpm, = self.ax_bpm.plot([], [], color='magenta', lw=1.5)
        self.line_signal_filt, = self.ax_signal_filt.plot([], [], color='lime', lw=1.5)
        self.line_bpm_filt, = self.ax_bpm_filt.plot([], [], color='orange', lw=1.5)

        # Sembunyikan subplot filtered secara default
        self.ax_signal_filt.set_visible(False)
        self.ax_bpm_filt.set_visible(False)
        self.line_signal_filt.set_visible(False)
        self.line_bpm_filt.set_visible(False)

        self.canvas = FigureCanvasTkAgg(self.fig, master=right_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.fig.tight_layout()  # pastikan layout tidak tumpang tindih

    def _process_serial_queue(self):
        """
        Proses data dari queue serial, update buffer.
        """
        updated = False
        if not self.is_paused:
            while not self.serial_queue.empty():
                try:
                    current_time, value = self.serial_queue.get_nowait()
                except queue.Empty:
                    break
                is_beat = value > BPM_THRESHOLD and self.last_value <= BPM_THRESHOLD
                if is_beat and (current_time - self.last_beat_time > 0.25):
                    interval_ms = (current_time - self.last_beat_time) * 1000
                    instant_bpm = 60000 / interval_ms
                    if 40 < instant_bpm < 200:
                        self.beat_timestamps.append(instant_bpm)
                        if len(self.beat_timestamps) > BPM_AVG_WINDOW:
                            self.beat_timestamps = self.beat_timestamps[-BPM_AVG_WINDOW:]
                        self.current_bpm = np.mean(self.beat_timestamps)
                    self.last_beat_time = current_time
                t = current_time - self.start_time if self.start_time else 0
                # Simpan ke buffer, rolling window
                self.data_buffer.append((t, value, self.current_bpm))
                if len(self.data_buffer) > self.buffer_maxlen:
                    self.data_buffer = self.data_buffer[-self.buffer_maxlen:]
                if self.current_bpm > 0:
                    self.bpm_label_var.set(f"{int(self.current_bpm)}")
                self.last_value = value
                updated = True
        # Jadwalkan polling queue berikutnya
        if self.is_started:
            self.root.after(10, self._process_serial_queue)
        # Update plot/statistik secara periodik
        if updated and not self.is_paused:
            # Hanya jadwalkan update jika belum ada update berjalan
            if not hasattr(self, '_buffer_update_scheduled') or not self._buffer_update_scheduled:
                self._schedule_buffer_update()

    def _schedule_buffer_update(self):
        # Update plot/statistik dari buffer setiap interval tertentu
        if hasattr(self, '_buffer_update_scheduled') and self._buffer_update_scheduled:
            return  # Sudah dijadwalkan
        self._buffer_update_scheduled = True
        def update():
            self._buffer_update_scheduled = False
            self._update_plot_from_buffer()
            self._update_bpm_stats_from_buffer()
            self.canvas.draw_idle()
            if self.is_started:
                self._buffer_update_scheduled = True
                self.root.after(200, update)
        self.root.after(200, update)

    def butter_bandpass_filter(self, data, lowcut, highcut, fs, order=5):
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        b, a = butter(order, [low, high], btype='band')
        y = filtfilt(b, a, data)
        return y

    def notch_filter(self, data, notch_freq, fs, Q=30):
        b, a = iirnotch(notch_freq, Q, fs)
        y = filtfilt(b, a, data)
        return y

    def apply_filter(self, signal):
        # Parameter filter (bisa disesuaikan)
        FS = self.sampling_rate
        LOWCUT = 0.5
        HIGHCUT = 40.0
        NOTCH_FREQ = 50.0
        # Bandpass lalu notch
        bandpassed = self.butter_bandpass_filter(signal, LOWCUT, HIGHCUT, FS)
        filtered = self.notch_filter(bandpassed, NOTCH_FREQ, FS)
        return filtered

    def _update_plot_from_buffer(self):
        # Plot dari buffer, bukan DataFrame
        show_filtered = self.filter_enabled.get()
        # --- handle subplot visibility ---
        self.ax_signal_filt.set_visible(show_filtered)
        self.ax_bpm_filt.set_visible(show_filtered)
        self.line_signal_filt.set_visible(show_filtered)
        self.line_bpm_filt.set_visible(show_filtered)
        self.canvas.draw_idle()

        if not self.data_buffer:
            self.line_signal.set_data([], [])
            self.line_bpm.set_data([], [])
            self.line_signal_filt.set_data([], [])
            self.line_bpm_filt.set_data([], [])
            for ax in [self.ax_signal, self.ax_bpm, self.ax_signal_filt, self.ax_bpm_filt]:
                ax.set_xlim(0, 1)
            self.ax_signal.set_ylim(0, 1024)
            self.ax_bpm.set_ylim(0, 200)
            self.ax_signal_filt.set_ylim(0, 1024)
            self.ax_bpm_filt.set_ylim(0, 200)
            self.fig.tight_layout()
            return
        arr = np.array(self.data_buffer)
        t = arr[:, 0]
        y_signal = arr[:, 1]
        y_bpm = arr[:, 2]
        window_sec = self.plot_window_sec
        t_max = t[-1]
        t_min = max(0, t_max - window_sec)
        idx = t >= t_min
        t_win = t[idx]
        y_signal_win = y_signal[idx]
        y_bpm_win = y_bpm[idx]
        self.line_signal.set_data(t_win, y_signal_win)
        self.line_bpm.set_data(t_win, y_bpm_win)
        self.ax_signal.set_xlim(
            t_win[0] if len(t_win) > 0 else 0,
            t_win[-1] if len(t_win) > 0 else window_sec
        )
        self.ax_bpm.set_xlim(
            t_win[0] if len(t_win) > 0 else 0,
            t_win[-1] if len(t_win) > 0 else window_sec
        )
        if len(y_signal_win) > 0:
            y_min = min(y_signal_win)
            y_max = max(y_signal_win)
            pad = max(10, (y_max - y_min) * 0.1)
            self.ax_signal.set_ylim(y_min - pad, y_max + pad)
        else:
            self.ax_signal.set_ylim(0, 1024)
        if len(y_bpm_win) > 0:
            yb_min = min(y_bpm_win)
            yb_max = max(y_bpm_win)
            padb = max(5, (yb_max - yb_min) * 0.1)
            self.ax_bpm.set_ylim(max(0, yb_min - padb), yb_max + padb)
        else:
            self.ax_bpm.set_ylim(0, 200)
        self.ax_signal.set_xlabel("Waktu (detik)", color='white')
        self.ax_bpm.set_xlabel("Waktu (detik)", color='white')

        # --- FILTERED PLOT ---
        if show_filtered and len(y_signal_win) > 10:
            try:
                y_signal_filt = self.apply_filter(y_signal_win)
            except Exception:
                y_signal_filt = y_signal_win  # fallback jika error
            self.filtered_buffer = list(zip(t_win, y_signal_filt, y_bpm_win))
        else:
            y_signal_filt = []
            self.filtered_buffer = []
        self.line_signal_filt.set_data(t_win, y_signal_filt)
        self.line_bpm_filt.set_data(t_win, y_bpm_win)
        self.ax_signal_filt.set_xlim(
            t_win[0] if len(t_win) > 0 else 0,
            t_win[-1] if len(t_win) > 0 else window_sec
        )
        self.ax_bpm_filt.set_xlim(
            t_win[0] if len(t_win) > 0 else 0,
            t_win[-1] if len(t_win) > 0 else window_sec
        )
        if len(y_signal_filt) > 0:
            y_min_f = min(y_signal_filt)
            y_max_f = max(y_signal_filt)
            pad_f = max(10, (y_max_f - y_min_f) * 0.1)
            self.ax_signal_filt.set_ylim(y_min_f - pad_f, y_max_f + pad_f)
        else:
            self.ax_signal_filt.set_ylim(0, 1024)
        if len(y_bpm_win) > 0:
            yb_min_f = min(y_bpm_win)
            yb_max_f = max(y_bpm_win)
            padb_f = max(5, (yb_max_f - yb_min_f) * 0.1)
            self.ax_bpm_filt.set_ylim(max(0, yb_min_f - padb_f), yb_max_f + padb_f)
        else:
            self.ax_bpm_filt.set_ylim(0, 200)
        self.ax_signal_filt.set_xlabel("Waktu (detik)", color='white')
        self.ax_bpm_filt.set_xlabel("Waktu (detik)", color='white')
        self.fig.tight_layout()

    def _update_bpm_stats_from_buffer(self):
        # Statistik BPM dari buffer, min tidak boleh nol, tampilkan jumlah data
        if self.data_buffer:
            arr = np.array(self.data_buffer)
            bpm_nonzero = arr[:, 2][arr[:, 2] > 0]
            count = len(bpm_nonzero)
            if count > 0:
                avg = np.mean(bpm_nonzero)
                mx = np.max(bpm_nonzero)
                mn = np.min(bpm_nonzero)
                self.bpm_stats_var.set(
                    f"Rata-rata: {avg:.1f}   Maks: {mx:.0f}   Min: {mn:.0f}   Jumlah: {count}"
                )
                return
        self.bpm_stats_var.set("Rata-rata: --   Maks: --   Min: --   Jumlah: 0")

    def start_task(self):
        if self.save_var.get():
            label = self.label_input.get().strip()
            gender = self.gender_var.get().lower()
            age = self.age_input.get().strip()
            condition = self.condition_var.get().lower()
            if not all([label, gender, age, condition]):
                messagebox.showwarning("Data Tidak Lengkap", "Harap isi semua informasi subjek.")
                return
            try: int(age)
            except ValueError:
                messagebox.showwarning("Input Salah", "Usia harus berupa angka.")
                return
            
            base_filename = f"{label}_{gender}_{age}_{condition}.csv"
            filename = self._get_unique_filename(base_filename)
            self.csv_filename = filename
        else:
            self.csv_filename = None

        self.is_started = True
        self.is_paused = False
        self.start_time = time.time()
        self.last_beat_time = 0
        self.beat_timestamps = []
        self.current_bpm = 0
        self.last_value = 0

        global SERIAL_PORT
        if SERIAL_PORT is None:
            SERIAL_PORT = detect_serial_port()
        if SERIAL_PORT is None:
            messagebox.showerror("Error Serial", "Tidak ada perangkat serial (Arduino) terdeteksi.")
            self.is_started = False
            return
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
        except serial.SerialException as e:
            messagebox.showerror("Error Serial", f"Gagal membuka port {SERIAL_PORT}: {e}")
            self.is_started = False
            return

        # Mulai thread serial
        self.serial_thread_stop.clear()
        self.serial_thread = threading.Thread(target=self._serial_worker, daemon=True)
        self.serial_thread.start()
        self.root.after(10, self._process_serial_queue)

        self.start_button.config(state=DISABLED)
        self.stop_button.config(state=NORMAL)
        self.pause_button.config(state=NORMAL, text="Pause")
        for widget in [self.label_input, self.gender_combo, self.age_input, self.condition_combo, self.save_checkbox]:
            widget.config(state=DISABLED)

    def stop_task(self):
        if not self.is_started: return
        self.is_started = False
        self.is_paused = False
        self.serial_thread_stop.set()
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        if self.serial_thread:
            self.serial_thread.join(timeout=1)
            self.serial_thread = None
        # Ekspor buffer ke CSV jika diminta
        if self.csv_filename:
            try:
                # Ekspor seluruh buffer ke DataFrame untuk simpan
                if self.data_buffer:
                    df_export = pd.DataFrame(self.data_buffer, columns=["time", "signal", "bpm"])
                    # Tambahkan kolom filtered jika filter aktif dan hasil tersedia
                    if self.filter_enabled.get() and self.data_buffer:
                        arr = np.array(self.data_buffer)
                        t = arr[:, 0]
                        y_signal = arr[:, 1]
                        if len(y_signal) > 10:
                            try:
                                y_signal_filt = self.apply_filter(y_signal)
                            except Exception:
                                y_signal_filt = y_signal
                            df_export["signal_filtered"] = y_signal_filt

                            # --- Tambahkan BPM hasil filtered ---
                            bpm_filtered = self._calculate_bpm_from_signal(t, y_signal_filt)
                            df_export["bpm_filtered"] = bpm_filtered
                    df_export.to_csv(self.csv_filename, index=False)
                self.last_subject_info = self._extract_subject_info_from_filename(self.csv_filename)
                self.last_subject_label_var.set(f"Subjek terakhir: {self.last_subject_info}")
                messagebox.showinfo("Info", f"Perekaman dihentikan dan file telah disimpan sebagai {self.csv_filename}.")
            except Exception as e:
                messagebox.showerror("Error File", f"Gagal menyimpan file: {e}")
            self.csv_filename = None
        self.start_button.config(state=NORMAL)
        self.stop_button.config(state=DISABLED)
        self.pause_button.config(state=DISABLED, text="Pause")
        for widget in [self.label_input, self.gender_combo, self.age_input, self.condition_combo, self.save_checkbox]:
            widget.config(state=NORMAL)

    def _calculate_bpm_from_signal(self, t, signal):
        """
        Hitung BPM dari sinyal (filtered) menggunakan threshold dan deteksi beat sederhana.
        """
        threshold = BPM_THRESHOLD
        min_interval = 0.25  # detik, minimal antar beat
        last_beat_time = None
        beat_times = []
        bpm_list = []
        for i in range(1, len(signal)):
            if signal[i] > threshold and signal[i-1] <= threshold:
                if last_beat_time is None or (t[i] - last_beat_time) > min_interval:
                    beat_times.append(t[i])
                    last_beat_time = t[i]
            # Hitung BPM instan
            if len(beat_times) >= 2:
                interval = beat_times[-1] - beat_times[-2]
                if interval > 0:
                    bpm = 60.0 / interval
                else:
                    bpm = 0
            else:
                bpm = 0
            bpm_list.append(bpm)
        # Panjang bpm_list = len(signal)-1, tambahkan 0 di depan agar sama panjang
        bpm_list = [0] + bpm_list
        return bpm_list

    def pause_task(self):
        if not self.is_started:
            return
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_button.config(text="Resume", bootstyle="warning")
        else:
            self.pause_button.config(text="Pause", bootstyle="secondary")
        # Tidak perlu menghentikan thread, hanya hentikan proses data

    def reset_plot(self):
        self.data_buffer.clear()
        self.filtered_buffer.clear()
        self.start_time = time.time() if self.is_started else None
        self.bpm_label_var.set("--")
        self._update_bpm_stats_from_buffer()
        self._update_plot_from_buffer()
        self.canvas.draw_idle()
        self.fig.tight_layout()

    def on_closing(self):
        if self.is_started:
            if messagebox.askyesno("Keluar", "Perekaman sedang berjalan. Yakin ingin keluar?"):
                self.stop_task()
                self.root.destroy()
        else:
            self.root.destroy()

    def _get_unique_filename(self, base_filename):
        """
        Cek apakah file sudah ada, jika ya tambahkan penomoran agar tidak overwrite.
        """
        name, ext = os.path.splitext(base_filename)
        counter = 1
        filename = base_filename
        while os.path.exists(filename):
            filename = f"{name}_{counter}{ext}"
            counter += 1
        return filename

    def _extract_subject_info_from_filename(self, filename):
        basename = os.path.basename(filename)
        name = basename.replace('.csv', '')
        parts = name.split('_')
        if len(parts) >= 4:
            label = parts[0]
            gender = parts[1]
            age = parts[2]
            condition = '_'.join(parts[3:])
            return f"{label}, {gender}, {age}, {condition}"
        return basename

    def _serial_worker(self):
        """
        Worker thread untuk membaca data serial dan memasukkan ke queue.
        """
        try:
            while not self.serial_thread_stop.is_set() and self.ser and self.ser.is_open:
                if self.is_paused:
                    time.sleep(0.05)
                    continue
                while self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8').strip()
                    if not line or line == '!':
                        continue
                    try:
                        value = int(line)
                    except ValueError:
                        continue
                    current_time = time.time()
                    self.serial_queue.put((current_time, value))
                time.sleep(0.002)  # Hindari busy loop
        except Exception:
            pass

    def _on_filter_toggle(self):
        self._update_plot_from_buffer()
        self.canvas.draw_idle()

if __name__ == "__main__":
    root = ttk.Window(themename=THEME_NAME)
    app = EkgApp(root)
    root.mainloop()