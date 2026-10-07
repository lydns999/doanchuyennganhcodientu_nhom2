"""
r = reselect   q = quit
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import serial
import serial.tools.list_ports
import torch
from ultralytics import YOLO

USE_SERIAL = True            # False = de test khong co esp32
SERIAL_PORT = "auto"         # auto hoac port
BAUD = 115200

CAM_INDEX = 1                # C270 = 1 webcam = 0
FRAME_W, FRAME_H = 640, 480

MODEL_PATH = r"runs\detect\hand\weights\best.pt"   # model train
CONF = 0.4                   
IMGSZ = 640
MIN_OVERLAP = 0.10           

CONFIRM_FRAMES = 2           
HOLD_SEC = 0.8               
SEND_INTERVAL = 0.1          

ROI_FILE = Path("roi.json")
DEVICE = 0 if torch.cuda.is_available() else "cpu"
USE_HALF = DEVICE != "cpu"


def find_port():
    """Pick the first USB-serial adapter that looks like an ESP32 board."""
    keys = ("CP210", "CH340", "CH910", "USB-SERIAL", "USB SERIAL", "SILICON LABS", "ESP32")
    for p in serial.tools.list_ports.comports():
        text = f"{p.description} {p.manufacturer}".upper()
        if any(k in text for k in keys):
            return p.device
    return None


def open_serial():
    port = find_port() if SERIAL_PORT == "auto" else SERIAL_PORT
    if port is None:
        print("No ESP32 serial port found. Check the cable/driver, or set USE_SERIAL = False.")
        print("Ports seen:", [p.device for p in serial.tools.list_ports.comports()])
        return None
    try:
        ser = serial.Serial(port, BAUD, timeout=0)
    except serial.SerialException as e:
        print(f"Cannot open {port}: {e}")
        return None
    print("Serial port:", port)
    time.sleep(2)  
    return ser


def open_camera():
    if sys.platform.startswith("win"):
        cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(CAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)          
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)   
    return cap


def select_roi(frame):
    win = "Select danger zone (drag, ENTER to confirm)"
    x, y, w, h = cv2.selectROI(win, frame, False)
    cv2.destroyWindow(win)
    roi = (int(x), int(y), int(x + w), int(y + h))
    ROI_FILE.write_text(json.dumps(roi))
    return roi


def load_roi():
    if ROI_FILE.exists():
        try:
            v = json.loads(ROI_FILE.read_text())
            if len(v) == 4:
                return tuple(int(i) for i in v)
        except Exception:
            pass
    return None


def overlap_ratio(box, roi):
    """Fraction of the hand box area that lies inside the ROI."""
    bx1, by1, bx2, by2 = box
    rx1, ry1, rx2, ry2 = roi
    iw = min(bx2, rx2) - max(bx1, rx1)
    ih = min(by2, ry2) - max(by1, ry1)
    if iw <= 0 or ih <= 0:
        return 0.0
    area = max(1, (bx2 - bx1) * (by2 - by1))
    return (iw * ih) / area


def main():
    if not Path(MODEL_PATH).exists():
        print(f"Model not found: {MODEL_PATH}")
        print("Train it with train_hand.py first, or point MODEL_PATH to your best.pt")
        return

    ser = None
    if USE_SERIAL:
        ser = open_serial()
        if ser is None:
            return
    else:
        print("USE_SERIAL = False: test mode, nothing is sent to the ESP32/PLC")

    def send(b):
        if ser is not None:
            ser.write(b)

    print("YOLO device:", DEVICE)
    model = YOLO(MODEL_PATH)
    model(np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8),
          device=DEVICE, half=USE_HALF, verbose=False)  # warm-up

    cap = open_camera()
    ok, frame = cap.read()
    if not ok:
        print("Cannot read from camera (check CAM_INDEX / other apps using the camera)")
        send(b"D")
        return

    roi = load_roi() or select_roi(frame)

    consecutive = 0
    last_danger_time = 0.0
    last_send = 0.0
    fps, t_prev = 0.0, time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                send(b"D")          
                time.sleep(0.1)
                continue

            res = model(frame, classes=[0], conf=CONF, imgsz=IMGSZ,
                        device=DEVICE, half=USE_HALF, verbose=False)[0]

            hand_in_roi = False
            for box, conf in zip(res.boxes.xyxy.cpu().numpy(), res.boxes.conf.cpu().numpy()):
                x1, y1, x2, y2 = map(int, box)
                inside = overlap_ratio((x1, y1, x2, y2), roi) >= MIN_OVERLAP
                hand_in_roi |= inside
                color = (0, 0, 255) if inside else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"hand {conf:.2f}", (x1, max(15, y1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            consecutive = consecutive + 1 if hand_in_roi else 0
            now = time.time()
            if consecutive >= CONFIRM_FRAMES:
                last_danger_time = now
            danger = (now - last_danger_time) < HOLD_SEC

            if now - last_send >= SEND_INTERVAL:     
                send(b"D" if danger else b"S")
                last_send = now

            fps = 0.9 * fps + 0.1 * (1.0 / max(1e-6, now - t_prev))
            t_prev = now

            color = (0, 0, 255) if danger else (0, 200, 0)
            cv2.rectangle(frame, roi[:2], roi[2:], color, 2)
            cv2.putText(frame, "DANGER" if danger else "SAFE", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            cv2.putText(frame, f"{fps:.0f} FPS", (10, 58),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.imshow("Hand danger zone", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                roi = select_roi(frame)
    finally:
        try:
            send(b"D")               
        except Exception:
            pass
        cap.release()
        cv2.destroyAllWindows()
        if ser is not None:
            ser.close()


if __name__ == "__main__":
    main()
