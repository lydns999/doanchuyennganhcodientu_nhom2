// dem_vat_wifi.ino - Dem vat bang 1 cam bien E3F, gui so dem len giao dien qua Wi-Fi
// TRANG THAI: viet truoc, CHUA thu tren phan cung.
//
// ESP32 dem vat o che do doc lap. Cu 0,4 giay gui ban tin $CNT,<so_dem>,<dang_dem>,<ms>*CS
// toi server.py (POST /api/line). Phan hoi cua server co the kem lenh:
//   COUNT_ON (bat dem), COUNT_OFF (tat dem), COUNT_RESET (dua so dem ve 0).
// Mat Wi-Fi thi van dem binh thuong, chi giao dien khong cap nhat.
//
// Cach dung:
//  1. Sao chep config_mau.h thanh config.h, dien ten Wi-Fi, mat khau, dia chi IPv4 cua may tinh.
//  2. May tinh chay: python server.py   (cho phep Python qua tuong lua khi Windows hoi, chon mang Private)
//  3. Nap chuong trinh nay len ESP32, mo giao dien http://localhost:8000, chon tab "Dem vat".
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "config.h"

// ---- Chan va tham so ----
const int PIN_E3F = 32;               // NPN thuong ho: co vat -> muc LOW; dung dien tro keo len ben trong ESP32
const int ACTIVE_LEVEL = LOW;
const uint32_t DEBOUNCE_MS = 10;      // loc nhieu: trang thai phai on dinh tu ngan nay
const uint32_t MIN_GAP_MS = 150;      // hai lan bat gan hon ngan nay chi tinh la 1 vat
const uint32_t SEND_PERIOD_MS = 400;

// ---- Trang thai dung chung giua 2 tac vu ----
volatile uint32_t demSo = 0;
volatile bool dangDem = true;

// ---- Cam bien ----
bool raw = false, state = false;
uint32_t tRaw = 0, tLastCount = 0;

uint8_t checksum(const char* body) {
  uint8_t cs = 0;
  while (*body) cs ^= (uint8_t)*body++;
  return cs;
}

// Tac vu mang chay rieng, de cho phan hoi cua server khong lam do cam bien
void taskMang(void*) {
  String url = String("http://") + SERVER_IP + ":" + SERVER_PORT + "/api/line";
  for (;;) {
    if (WiFi.status() == WL_CONNECTED) {
      char body[48], line[64];
      snprintf(body, sizeof(body), "CNT,%lu,%d,%lu", (unsigned long)demSo, dangDem ? 1 : 0, (unsigned long)millis());
      snprintf(line, sizeof(line), "$%s*%02X", body, checksum(body));
      HTTPClient http;
      http.setTimeout(800);
      if (http.begin(url)) {
        http.addHeader("Content-Type", "text/plain");
        int code = http.POST((uint8_t*)line, strlen(line));
        if (code == 200) {
          String r = http.getString();
          if (r.indexOf("COUNT_ON") >= 0) { dangDem = true; Serial.println("# lenh: bat dem"); }
          else if (r.indexOf("COUNT_OFF") >= 0) { dangDem = false; Serial.println("# lenh: tat dem"); }
          else if (r.indexOf("COUNT_RESET") >= 0) { demSo = 0; Serial.println("# lenh: reset so dem"); }
        }
        http.end();
      }
    }
    vTaskDelay(SEND_PERIOD_MS / portTICK_PERIOD_MS);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_E3F, INPUT_PULLUP);
  raw = state = (digitalRead(PIN_E3F) == ACTIVE_LEVEL);
  tRaw = millis();
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  xTaskCreatePinnedToCore(taskMang, "mang", 8192, NULL, 1, NULL, 0);
  Serial.println("# dem_vat_wifi: san sang");
}

void loop() {
  uint32_t now = millis();
  bool r = (digitalRead(PIN_E3F) == ACTIVE_LEVEL);
  if (r != raw) { raw = r; tRaw = now; }
  if (raw != state && now - tRaw >= DEBOUNCE_MS) {
    state = raw;
    if (state && dangDem && now - tLastCount >= MIN_GAP_MS) {   // vat vua toi
      demSo = demSo + 1;
      tLastCount = now;
      Serial.printf("# dem: %lu\n", (unsigned long)demSo);
    }
  }
  static uint32_t tWifi = 0;
  if (now - tWifi > 5000) {
    tWifi = now;
    Serial.println(WiFi.status() == WL_CONNECTED ? "# Wi-Fi: da ket noi" : "# Wi-Fi: chua ket noi");
  }
  delay(1);
}
