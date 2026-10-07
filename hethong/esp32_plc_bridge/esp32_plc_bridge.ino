/*
  ESP32 bridge: PC (YOLO) -> serial -> opto/relay -> PLC FX1S input X

  Serial protocol (115200 baud), one byte at a time:
    'S' = safe, 'D' = danger
  The PC must send a byte at least every ~100 ms (heartbeat).
  If nothing is received for TIMEOUT_MS, or after power-up, the state is DANGER.

  Output polarity (fail-safe by default):
    SAFE   -> PIN_OUT = HIGH -> relay/opto ON  -> PLC input X = ON
    DANGER -> PIN_OUT = LOW  -> relay/opto OFF -> PLC input X = OFF
  So if the ESP32 loses power, the cable is pulled, or the PC hangs,
  X turns OFF and the PLC must treat X = OFF as DANGER.
  If your ladder is written the other way round (X ON = danger),
  set SAFE_IS_HIGH to false, but you lose the "power loss = danger" protection.
*/

const int PIN_OUT = 26;                 // to opto/relay module IN
const int PIN_LED = 2;                  // onboard LED: ON = danger
const unsigned long TIMEOUT_MS = 700;   // heartbeat timeout
const bool SAFE_IS_HIGH = true;

bool danger = true;
bool everReceived = false;
unsigned long lastRx = 0;

void applyOutput(bool d) {
  bool high = d ? !SAFE_IS_HIGH : SAFE_IS_HIGH;
  digitalWrite(PIN_OUT, high ? HIGH : LOW);
  digitalWrite(PIN_LED, d ? HIGH : LOW);
}

void setup() {
  pinMode(PIN_OUT, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  applyOutput(true);          // start in DANGER
  Serial.begin(115200);
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == 'S') {
      danger = false;
      lastRx = millis();
      everReceived = true;
    } else if (c == 'D') {
      danger = true;
      lastRx = millis();
      everReceived = true;
    }
  }

  bool timedOut = !everReceived || (millis() - lastRx > TIMEOUT_MS);
  applyOutput(danger || timedOut);
}
