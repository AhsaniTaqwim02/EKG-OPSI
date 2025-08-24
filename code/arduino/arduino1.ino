const int heartPin = A0; // Pin sinyal dari AD8232
unsigned long lastSampleTime = 0;
int samplingInterval = 40; // 40 ms = 25 Hz

void setup() {
  Serial.begin(9600);
  pinMode(heartPin, INPUT);
  Serial.println("Mulai pemantauan detak jantung...");
}

void loop() {
  // Sampling setiap 40 ms
  if (millis() - lastSampleTime >= samplingInterval) {
    lastSampleTime = millis();

    int signal = analogRead(heartPin);
    Serial.println(signal); // Kirim hanya angka agar grafik bersih
  }

  // Jangan pakai delay() agar sampling presisi
}
