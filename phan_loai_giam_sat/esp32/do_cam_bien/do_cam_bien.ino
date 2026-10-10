// do_cam_bien.ino - Chuong trinh do 2 cam bien E3F-DS30C4 va LJ12A3-4-Z/BX
// TRANG THAI: viet truoc, CHUA thu tren phan cung.
//
// Muc dich: ghi lai thoi diem moi cam bien doi trang thai va do rong xung (ms) khi co vat di qua,
// kem ten vat lieu dang thu, de lap bang do (data/do_cam_bien.csv).
// Chuong trinh nay khong phan loai va khong dieu khien co cau day.
//
// Cach dung:
//  1. Nap len ESP32, mo Serial Monitor 115200 baud, chon "Newline".
//  2. Go mot ky tu de chon vat lieu dang thu (go h de xem danh sach).
//  3. Dua vat qua cam bien; moi lan doi trang thai in ra mot dong CSV.
//  4. Copy cac dong bat dau bang "CSV," vao file data/do_cam_bien.csv.
#include <Arduino.h>

// ---- Chan va kieu noi (chinh o day neu doi day) ----
const int PIN_E3F = 32;   // NPN 3 day: co vat -> keo xuong muc LOW; tro keo len 3V3 10k
const int PIN_LJ  = 33;
const int ACTIVE_LEVEL = LOW;   // muc doc duoc khi cam bien "bat"

const uint32_t DEBOUNCE_MS = 5;

struct Sensor {
  const char* name;
  int pin;
  bool raw, state;      // state = true khi cam bien dang bat
  uint32_t tRaw, tOn;
  void begin() {
    pinMode(pin, INPUT);              // da co tro keo len ngoai; neu khong co: doi thanh INPUT_PULLUP khi thu tren ban
    raw = state = (digitalRead(pin) == ACTIVE_LEVEL);
    tRaw = tOn = millis();
  }
};

Sensor sensors[2] = {
  {"E3F", PIN_E3F, false, false, 0, 0},
  {"LJ12A3", PIN_LJ, false, false, 0, 0},
};

char material = '0';   // '0' = chua chon
const char* materialName(char c) {
  switch (c) {
    case 't': return "thep";
    case 'i': return "inox";
    case 'a': return "nhom";
    case 'd': return "dong";
    case 'p': return "nhua";
    case 'g': return "go";
    default:  return "chua_chon";
  }
}

void printHelp() {
  Serial.println("# Chon vat lieu: t=thep i=inox a=nhom d=dong p=nhua g=go 0=chua chon");
  Serial.println("# Cot: CSV,thoi_diem_ms,vat_lieu,cam_bien,su_kien,rong_xung_ms");
}

void report(const Sensor& s, bool on, uint32_t now) {
  char buf[96];
  if (on) {
    snprintf(buf, sizeof(buf), "CSV,%lu,%s,%s,bat,", (unsigned long)now, materialName(material), s.name);
  } else {
    snprintf(buf, sizeof(buf), "CSV,%lu,%s,%s,tat,%lu", (unsigned long)now, materialName(material), s.name,
             (unsigned long)(now - s.tOn));
  }
  Serial.println(buf);
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 2; i++) sensors[i].begin();
  Serial.println("# do_cam_bien: san sang");
  printHelp();
}

void loop() {
  uint32_t now = millis();
  for (int i = 0; i < 2; i++) {
    Sensor& s = sensors[i];
    bool r = (digitalRead(s.pin) == ACTIVE_LEVEL);
    if (r != s.raw) { s.raw = r; s.tRaw = now; }
    if (s.raw != s.state && now - s.tRaw >= DEBOUNCE_MS) {
      s.state = s.raw;
      if (s.state) s.tOn = now;
      report(s, s.state, now);
    }
  }
  while (Serial.available()) {
    int c = Serial.read();
    if (c == '\n' || c == '\r' || c == ' ') continue;
    if (c == 'h') { printHelp(); continue; }
    if (c == '0' || c == 't' || c == 'i' || c == 'a' || c == 'd' || c == 'p' || c == 'g') {
      material = (char)c;
      char buf[48];
      snprintf(buf, sizeof(buf), "# vat lieu: %s", materialName(material));
      Serial.println(buf);
    }
  }
}
