import sys
import time

import cv2
import numpy as np
import serial
import torch
from ultralytics import YOLO


SERIAL_PORT = "COM5"        
BAUD = 115200
CAM_INDEX = 0
FRAME_W, FRAME_H = 640, 480
MODEL_PATH = "yolov8n.pt"   
CONF = 0.5
IMGSZ = 640
CONFIRM_FRAMES = 3          
HOLD_SEC = 1.0              
SEND_INTERVAL = 0.1         
DEVICE = 0 if torch.cuda.is_available() else "cpu"   
USE_HALF = DEVICE != "cpu"  


def open_camera():
    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW) if sys.platform.startswith("win") \
        else cv2.VideoCapture(CAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  
    return cap


def select_roi(frame):
    x, y, w, h = cv2.selectROI("Select danger zone (ENTER to confirm)", frame, False)
    cv2.destroyWindow("Select danger zone (ENTER to confirm)")
    return (int(x), int(y), int(x + w), int(y + h))


def intersects(box, roi):
    bx1, by1, bx2, by2 = box
    rx1, ry1, rx2, ry2 = roi
    return not (bx2 < rx1 or bx1 > rx2 or by2 < ry1 or by1 > ry2)


def main():
    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0)
    time.sleep(2)  

    print("YOLO device:", DEVICE)
    model = YOLO(MODEL_PATH)
    dummy = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    model(dummy, device=DEVICE, half=USE_HALF, verbose=False)  # warm-up
    cap = open_camera()

    ok, frame = cap.read()
    if not ok:
        print("Cannot read from camera")
        ser.write(b"D")
        return
    roi = select_roi(frame)

    consecutive = 0
    last_danger_time = 0.0
    last_send = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                ser.write(b"D")  
                time.sleep(0.1)
                continue

            res = model(frame, classes=[0], conf=CONF, imgsz=IMGSZ,
                        device=DEVICE, half=USE_HALF, verbose=False)[0]
            person_in_roi = False
            for box in res.boxes.xyxy.cpu().numpy():
                x1, y1, x2, y2 = map(int, box)
                inside = intersects((x1, y1, x2, y2), roi)
                person_in_roi |= inside
                color = (0, 0, 255) if inside else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            consecutive = consecutive + 1 if person_in_roi else 0
            now = time.time()
            if consecutive >= CONFIRM_FRAMES:
                last_danger_time = now
            danger = (now - last_danger_time) < HOLD_SEC

            if now - last_send >= SEND_INTERVAL:
                ser.write(b"D" if danger else b"S")
                last_send = now

            cv2.rectangle(frame, roi[:2], roi[2:], (0, 0, 255) if danger else (255, 200, 0), 2)
            cv2.putText(frame, "DANGER" if danger else "SAFE", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1,
                        (0, 0, 255) if danger else (0, 200, 0), 2)
            cv2.imshow("Danger zone", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                roi = select_roi(frame)
    finally:
        try:
            ser.write(b"D")  
        except Exception:
            pass
        cap.release()
        cv2.destroyAllWindows()
        ser.close()


if __name__ == "__main__":
    main()