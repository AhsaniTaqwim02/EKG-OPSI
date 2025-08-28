/******************************************************************************
 * EKG_Signal_Generator.ino
 * * Deskripsi:
 * Kode ini menghasilkan sinyal EKG palsu (dummy) untuk tujuan pengujian
 * software di sisi komputer (Python, Processing, dll.) tanpa memerlukan 
 * sensor AD8232 fisik.
 * * Fitur:
 * - Menghasilkan bentuk gelombang P-QRS-T yang realistis.
 * - Berjalan pada ~1000 Hz (interval 1 ms).
 * - Menambahkan noise yang umum ditemukan:
 * 1. Dengung Listrik (Powerline Interference) @ 50 Hz.
 * 2. Geseran Garis Dasar (Baseline Wander).
 * 3. Noise acak.
 * - Menggunakan timer `micros()` untuk timing yang presisi, bukan `delay()`.
 * ******************************************************************************/

// --- KONFIGURASI SINYAL ---
const int BPM = 75;              // Denyut per menit yang disimulasikan
const int SAMPLE_RATE_HZ = 250; // Laju sampling (1000 Hz = interval 1 ms)

// Array yang merepresentasikan satu bentuk gelombang P-QRS-T yang bersih
// Dibuat secara manual untuk meniru bentuk EKG. Terpusat di 512 (nilai tengah ADC).
const int EKG_BEAT[] = {
  512, 512, 512, 515, 520, 522, 520, 515, 512, // P wave start
  510, 508, 512, 512,                           // PR segment
  505, 480, 450, 400, 350, 450, 750, 950, 700, 500, // QRS complex
  512, 512, 515, 525, 540, 550, 555, 550, 540, 525, 515, 512, // T wave
  512, 512, 512, 512, 512, 512, 512, 512, 512, 512  // Isoelectric line
};
const int BEAT_LENGTH = sizeof(EKG_BEAT) / sizeof(int);

// --- Variabel untuk Timing dan Looping ---
unsigned long lastSampleTime = 0;
const unsigned long SAMPLE_INTERVAL_US = 1000000 / SAMPLE_RATE_HZ; // Interval dalam mikrodetik
int beatIndex = 0;
int samplesPerBeat; // Akan dihitung di setup()

void setup() {
  Serial.begin(9600); // Pastikan baud rate ini sama dengan di Python
  
  // Hitung berapa banyak sampel yang dibutuhkan untuk satu siklus detak jantung
  // (60 detik / BPM) * laju sampling
  samplesPerBeat = (60.0 / BPM) * SAMPLE_RATE_HZ;
}

void loop() {
  // Gunakan micros() untuk timing yang presisi, HINDARI delay()
  unsigned long currentTime = micros();
  if (currentTime - lastSampleTime >= SAMPLE_INTERVAL_US) {
    lastSampleTime = currentTime; // Reset timer untuk sampel berikutnya
    
    int cleanSignal;
    
    // Jika kita masih dalam bagian P-QRS-T dari detak jantung
    if (beatIndex < BEAT_LENGTH) {
      cleanSignal = EKG_BEAT[beatIndex];
    } 
    // Jika kita berada di garis datar antara detak jantung
    else {
      cleanSignal = 512; // Nilai baseline
    }
    
    // --- TAMBAHKAN NOISE UNTUK MEMBUATNYA REALISTIS ---
    float time_s = (float)millis() / 1000.0; // Waktu dalam detik untuk fungsi sinus
    
    // 1. Noise Geseran Garis Dasar (frekuensi rendah)
    float baselineWander = 30.0 * sin(2 * PI * 0.3 * time_s);
    
    // 2. Noise Dengung Listrik 50 Hz (frekuensi tinggi)
    float powerlineNoise = 25.0 * sin(2 * PI * 50.0 * time_s);
    
    // 3. Noise Acak
    int randomNoise = random(-8, 9);
    
    // Gabungkan semuanya
    int finalSignal = cleanSignal + baselineWander + powerlineNoise + randomNoise;
    
    // Pastikan sinyal tetap dalam rentang 0-1023
    finalSignal = constrain(finalSignal, 0, 1023);
    
    // Kirim data ke port serial, sama seperti sensor asli
    Serial.println(finalSignal);
    
    // Pindah ke sampel berikutnya
    beatIndex++;
    
    // Jika satu siklus detak jantung selesai, reset untuk memulai detak baru
    if (beatIndex >= samplesPerBeat) {
      beatIndex = 0;
    }
  }
}