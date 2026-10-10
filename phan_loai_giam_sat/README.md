# Phân loại trên băng chuyền và giám sát

Phần việc của Đỗ Văn Lực trong đề tài "Hệ thống phát hiện và cảnh báo vật cản trong vùng nguy hiểm" (Nhóm 2).

## Nội dung hiện có

| Thư mục / file | Mô tả | Trạng thái |
|---|---|---|
| `esp32/do_cam_bien/do_cam_bien.ino` | Đo hai cảm biến E3F-DS30C4 (quang) và LJ12A3-4-Z/BX (tiệm cận cảm ứng): ghi thời điểm bật, tắt và độ rộng xung | Đã biên dịch trên Arduino IDE 2.3.8 (board ESP32 Dev Module), chưa thử trên phần cứng |
| `data/do_cam_bien.csv` | Bảng ghi số đo | Chưa có số đo, chờ cảm biến |

## Cách dùng chương trình đo

1. Nạp `do_cam_bien.ino` lên ESP32 bằng Arduino IDE.
2. Mở Serial Monitor, tốc độ 115200, chọn "Newline".
3. Gõ một ký tự rồi Enter để chọn vật liệu đang thử:
   `t` thép, `i` inox, `a` nhôm, `d` đồng, `p` nhựa, `g` gỗ, `0` chưa chọn, `h` xem hướng dẫn.
4. Đưa vật qua cảm biến. Mỗi lần cảm biến bật hoặc tắt, chương trình in một dòng:
   `CSV,thời_điểm_ms,vật_liệu,cảm_biến,sự_kiện,rộng_xung_ms`
5. Copy các dòng bắt đầu bằng `CSV,` vào `data/do_cam_bien.csv`.

## Nối dây (dự kiến, chưa kiểm tra)

- E3F: ngõ ra NPN nối chân GPIO 32, có điện trở kéo lên 3V3 10 kΩ.
- LJ12A3: ngõ ra NPN nối chân GPIO 33, có điện trở kéo lên 3V3 10 kΩ.
- Cảm biến báo "có vật" khi chân xuống mức thấp. Chân và mức kích hoạt đặt ở đầu file `.ino`.

## Kế hoạch tiếp theo

- Đo cảm biến thật, điền bảng số đo và cập nhật trạng thái ở trên.
- Chương trình phân loại kim loại và phi kim, đếm vật.
- Giao diện giám sát trên máy tính.
