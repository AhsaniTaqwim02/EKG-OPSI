// Definisikan pin yang terhubung ke sensor AD8232
const int OUTPUT_PIN = A0; // Pin output sinyal EKG
const int LO_PLUS_PIN = 10;  // Pin Leads-Off Detection +
const int LO_MINUS_PIN = 11; // Pin Leads-Off Detection -

void setup() {
  // Mulai komunikasi serial dengan baud rate 9600
  // Pastikan baud rate ini sama dengan yang di program Python
  Serial.begin(9600);

  // Inisialisasi pin untuk deteksi elektroda terlepas
  pinMode(LO_PLUS_PIN, INPUT);
  pinMode(LO_MINUS_PIN, INPUT);
}

void loop() {
  // Memeriksa apakah elektroda terpasang dengan benar
  // Jika tidak, sinyal EKG tidak akan akurat
  if ((digitalRead(LO_PLUS_PIN) == 1) || (digitalRead(LO_MINUS_PIN) == 1)) {
    // Anda bisa mengirimkan sinyal error, misal nilai -1
    Serial.println(-1);
  } else {
    // Jika elektroda terpasang, baca nilai analog dari sensor
    int ekgValue = analogRead(OUTPUT_PIN);
    
    // Kirim nilai yang dibaca ke port serial
    Serial.println(ekgValue);
  }
  
  // Beri jeda singkat untuk mengatur laju sampling (sampling rate)
  // delay(2) kira-kira menghasilkan sampling rate ~500 Hz, yang cukup baik untuk EKG
  // Untuk data yang lebih stabil, disarankan menggunakan timer interrupt, tapi delay sudah cukup untuk memulai.
  delay(2); 
}