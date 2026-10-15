# Phân loại trên băng chuyền và giám sát

Phần việc của Đỗ Văn Lực trong đề tài "Hệ thống phát hiện và cảnh báo vật cản trong vùng nguy hiểm" (Nhóm 2).

Hiện có hai phần thử nghiệm độc lập, dùng hai chương trình ESP32 khác nhau (nạp một chương trình tại một thời điểm):

| Phần | Mục đích | Cảm biến | Cách truyền dữ liệu | Trạng thái |
|---|---|---|---|---|
| 1. Đo hai cảm biến | Đo đặc tính E3F và LJ12A3 với từng vật liệu | E3F và LJ12A3 | Cổng serial (USB), ghi tay vào bảng | Đã đo với cảm biến thật, đã điền số đo |
| 2. Đếm vật qua Wi-Fi | Thử đường giao tiếp ESP32 và giao diện | Chỉ E3F | Wi-Fi, trang web | Đã thử: đếm được và điều khiển được từ giao diện |

## Phần 1. Đo hai cảm biến

Thư mục / file:
- `esp32/do_cam_bien/do_cam_bien.ino`: đo E3F-DS30C4 (quang) và LJ12A3-4-Z/BX (tiệm cận cảm ứng), ghi thời điểm bật, tắt và độ rộng xung. Đã biên dịch trên Arduino IDE 2.3.8 (board ESP32 Dev Module).
- `data/do_cam_bien.csv`: bảng số đo theo từng vật liệu.

Nối dây:
- E3F: ngõ ra NPN thường hở nối GPIO 32.
- LJ12A3: ngõ ra NPN thường hở nối GPIO 33.
- Cảm biến cấp nguồn 12V riêng, GND nối chung với ESP32. Không cấp 12V vào chân ESP32.

Cách dùng:
1. Nạp `do_cam_bien.ino` lên ESP32 bằng Arduino IDE.
2. Mở Serial Monitor, tốc độ 115200, chọn "Newline".
3. Gõ một ký tự rồi Enter để chọn vật liệu đang thử:
   `t` thép, `i` inox, `a` nhôm, `d` đồng, `p` nhựa, `g` gỗ, `0` chưa chọn, `h` xem hướng dẫn.
4. Đưa vật qua cảm biến. Mỗi lần cảm biến bật hoặc tắt, chương trình in một dòng:
   `CSV,thời_điểm_ms,vật_liệu,cảm_biến,sự_kiện,rộng_xung_ms`
5. Ghi số đo vào `data/do_cam_bien.csv`.

## Phần 2. Đếm vật qua Wi-Fi (thử giao tiếp ESP32 và giao diện)

Thư mục / file:
- `esp32/dem_vat_wifi/dem_vat_wifi.ino`: đếm vật bằng một cảm biến E3F, gửi số đếm qua Wi-Fi, nhận lệnh bật/tắt đếm và reset từ giao diện.
- `test_giao_tiep/`: server Python (`server_don_gian.py`) và trang web (`index.html`) hiển thị số đếm, có nút bật/tắt đếm và reset.

Nối dây:
- E3F: dây nâu vào nguồn 12V, dây xanh dương vào GND chung với ESP32, dây đen (ngõ ra NPN) vào GPIO 32.
- GPIO dùng điện trở kéo lên bên trong ESP32 (`INPUT_PULLUP`), không dùng điện trở ngoài.

Cách dùng:
1. Trong `esp32/dem_vat_wifi/`, sao chép `config_mau.h` thành `config.h`, điền tên Wi-Fi, mật khẩu và địa chỉ IPv4 của máy tính. File `config.h` không được đưa lên GitHub.
2. Nạp `dem_vat_wifi.ino` lên ESP32 bằng Arduino IDE.
3. Trên máy tính chạy `test_giao_tiep/chay_test.bat` (hoặc `python server_don_gian.py`), rồi mở `http://localhost:8000`.
4. Đưa vật qua cảm biến: số đếm tăng. Thử nút bật/tắt đếm và reset.

Cách hoạt động: ESP32 gửi `$CNT,<số_đếm>,<đang_đếm>,<ms>*CS` tới server mỗi 0,4 giây. Lệnh từ trang web được server xếp hàng và gửi lại trong phản hồi của lần gửi kế tiếp. Mất Wi-Fi thì ESP32 vẫn đếm.

## Kế hoạch tiếp theo

- Phân tích số đo ở Phần 1, chỉnh các ngưỡng thời gian cho chương trình phân loại.
- Chương trình phân loại kim loại và phi kim, đếm từng loại.
- Giao diện giám sát đầy đủ trên máy tính.
