import csv
import json
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import serial
import serial.tools.list_ports

try:
    import torch
    _CUDA = torch.cuda.is_available()
except ImportError:      
    _CUDA = False


DETECTOR = "yolo"       
USE_SERIAL = False            
SERIAL_PORT = "auto"        
BAUD = 115200

CAM_INDEX = 0                # C270 , cam  lap = 0
FRAME_W, FRAME_H = 640, 480

MODEL_PATH = r"runs\detect\hand\weights\best.pt"  
CONF = 0.4                   
MP_CONF = 0.5                
BOX_PAD = 0.15               
IMGSZ = 640

MIN_OVERLAP_DANGER = 0.05    
MIN_OVERLAP_WARNING = 0.10   
CONFIRM_FRAMES = 2           
HOLD_DANGER_SEC = 1.0        
HOLD_WARNING_SEC = 0.5
SEND_INTERVAL = 0.1          

ZONES_FILE = Path("zones.json")
LOG_FILE = Path("events.csv")
DEVICE = 0 if _CUDA else "cpu"
USE_HALF = False 


SAFE, WARNING, DANGER = 0, 1, 2
NAME = {SAFE: "SAFE", WARNING: "WARNING", DANGER: "DANGER"}
TEXT = {SAFE: "SAFE - GREEN", WARNING: "WARNING - YELLOW", DANGER: "DANGER - STOP CONVEYOR"}
CODE = {SAFE: b"S", WARNING: b"W", DANGER: b"D"}
BGR = {SAFE: (0, 190, 0), WARNING: (0, 210, 255), DANGER: (0, 0, 230)}



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


# ---------------------------------------------------------------- zones
def draw_polygon(frame, title, color, existing=()):
    """Let the user click a polygon on the frame. Returns a list of points or None (Esc)."""
    pts = []
    base = frame.copy()
    for poly, c in existing:
        cv2.polylines(base, [np.array(poly, np.int32)], True, c, 2)

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            pts.append((x, y))
        elif event == cv2.EVENT_RBUTTONDOWN and pts:
            pts.pop()

    cv2.namedWindow(title)
    cv2.setMouseCallback(title, on_mouse)
    result = None
    while True:
        view = base.copy()
        for p in pts:
            cv2.circle(view, p, 4, color, -1)
        if len(pts) >= 2:
            cv2.polylines(view, [np.array(pts, np.int32)], len(pts) >= 3, color, 2)
        cv2.putText(view, f"{title}: click points, ENTER = done, Backspace/right-click = undo, Esc = skip",
                    (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        cv2.imshow(title, view)
        k = cv2.waitKey(20) & 0xFF
        if k in (13, 10) and len(pts) >= 3:
            result = list(pts)
            break
        if k == 27:
            break
        if k == 8 and pts:
            pts.pop()
    cv2.destroyWindow(title)
    return result


def setup_zones(frame, old=None):
    zones = dict(old) if old else {}
    d = draw_polygon(frame, "1) DANGER zone (red)", BGR[DANGER])
    if d:
        zones["danger"] = d
    existing = [(zones["danger"], BGR[DANGER])] if "danger" in zones else []
    w = draw_polygon(frame, "2) WARNING zone (yellow)", BGR[WARNING], existing)
    if w:
        zones["warning"] = w
    if "danger" in zones and "warning" in zones:
        ZONES_FILE.write_text(json.dumps(zones))
    return zones


def load_zones():
    if ZONES_FILE.exists():
        try:
            z = json.loads(ZONES_FILE.read_text())
            if "danger" in z and "warning" in z:
                return z
        except Exception:
            pass
    return None


def build_masks(zones, shape):
    """Binary masks for each zone and a coloured layer used for the overlay."""
    h, w = shape[:2]
    masks, layer = {}, np.zeros((h, w, 3), np.uint8)
    for level, key in ((WARNING, "warning"), (DANGER, "danger")):   
        m = np.zeros((h, w), np.uint8)
        cv2.fillPoly(m, [np.array(zones[key], np.int32)], 1)
        masks[level] = m
        layer[m > 0] = BGR[level]
    any_zone = (masks[WARNING] > 0) | (masks[DANGER] > 0)
    return masks, layer, any_zone


def classify_hand(box, masks, shape):
    """Return (level, overlap_danger, overlap_warning) for one hand box."""
    h, w = shape[:2]
    x1, y1, x2, y2 = box
    x1, x2 = max(0, x1), min(w, x2)
    y1, y2 = max(0, y1), min(h, y2)
    area = (x2 - x1) * (y2 - y1)
    if area <= 0:
        return SAFE, 0.0, 0.0
    od = np.count_nonzero(masks[DANGER][y1:y2, x1:x2]) / area
    ow = np.count_nonzero(masks[WARNING][y1:y2, x1:x2]) / area
    if od >= MIN_OVERLAP_DANGER:
        return DANGER, od, ow
    if ow >= MIN_OVERLAP_WARNING:
        return WARNING, od, ow
    return SAFE, od, ow


class YoloDetector:
    def __init__(self):
        if not Path(MODEL_PATH).exists():
            raise SystemExit(f"Model not found: {MODEL_PATH}\n"
                             "Train it with train_hand.py, or set DETECTOR = \"mediapipe\".")
        from ultralytics import YOLO
        print("YOLO device:", DEVICE)
        self.model = YOLO(MODEL_PATH)
        self.model(np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8),
                   device=DEVICE, half=USE_HALF, verbose=False)  

    def detect(self, frame):
        res = self.model(frame, classes=[0], conf=CONF, imgsz=IMGSZ,
                         device=DEVICE, half=USE_HALF, verbose=False)[0]
        out = []
        for box, c in zip(res.boxes.xyxy.cpu().numpy(), res.boxes.conf.cpu().numpy()):
            x1, y1, x2, y2 = map(int, box)
            out.append((x1, y1, x2, y2, float(c)))
        return out


class MediaPipeDetector:
    def __init__(self):
        try:
            import mediapipe as mp
            self.hands = mp.solutions.hands.Hands(
                static_image_mode=False, max_num_hands=2, model_complexity=0,
                min_detection_confidence=MP_CONF, min_tracking_confidence=0.5)
        except (ImportError, AttributeError):
            raise SystemExit("MediaPipe Hands is not available. Install the version that has it:\n"
                             "    pip install mediapipe==0.10.14")
        print("Detector: MediaPipe Hands (CPU)")

    def detect(self, frame):
        h, w = frame.shape[:2]
        res = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        out = []
        if res.multi_hand_landmarks:
            for i, hand in enumerate(res.multi_hand_landmarks):
                xs = [p.x * w for p in hand.landmark]
                ys = [p.y * h for p in hand.landmark]
                bw, bh = max(xs) - min(xs), max(ys) - min(ys)
                x1 = int(max(0, min(xs) - BOX_PAD * bw))
                y1 = int(max(0, min(ys) - BOX_PAD * bh))
                x2 = int(min(w - 1, max(xs) + BOX_PAD * bw))
                y2 = int(min(h - 1, max(ys) + BOX_PAD * bh))
                conf = res.multi_handedness[i].classification[0].score
                out.append((x1, y1, x2, y2, float(conf)))
        return out


def make_detector():
    return YoloDetector() if DETECTOR == "yolo" else MediaPipeDetector()



def log_event(events, state, n_hands):
    ts = datetime.now()
    events.appendleft(f"{ts:%H:%M:%S}  {NAME[state]}")
    new = not LOG_FILE.exists()
    try:
        with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            if new:
                wr.writerow(["time", "state", "hands_in_frame"])
            wr.writerow([ts.isoformat(timespec="seconds"), NAME[state], n_hands])
    except OSError:
        pass   


def draw_ui(frame, state, fps, dets_info, events):
    w = frame.shape[1]
    cv2.rectangle(frame, (0, 0), (w, 40), BGR[state], -1)
    cv2.putText(frame, TEXT[state], (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2)
    # tower-light indicator (red / yellow / green)
    for i, lvl in enumerate((DANGER, WARNING, SAFE)):
        centre = (w - 25 - i * 34, 20)
        on = state == lvl
        cv2.circle(frame, centre, 12, BGR[lvl] if on else (70, 70, 70), -1)
        cv2.circle(frame, centre, 12, (255, 255, 255), 1)
    cv2.putText(frame, f"{fps:.0f} FPS | {DETECTOR} | {dets_info}", (10, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    h = frame.shape[0]
    for i, line in enumerate(list(events)[:4]):
        cv2.putText(frame, line, (10, h - 10 - 16 * i), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (255, 255, 255), 1)



def main():
    detector = make_detector()

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

    cap = open_camera()
    ok, frame = cap.read()
    if not ok:
        print("Cannot read from camera (check CAM_INDEX / other apps using the camera)")
        send(b"D")
        return

    zones = load_zones() or setup_zones(frame)
    if "danger" not in zones or "warning" not in zones:
        print("Both zones are needed. Run again and draw the danger AND warning zones.")
        send(b"D")
        return
    masks, layer, any_zone = build_masks(zones, frame.shape)

    cnt = {WARNING: 0, DANGER: 0}
    last_seen = {WARNING: 0.0, DANGER: 0.0}
    state, prev_state = SAFE, None
    events = deque(maxlen=20)
    last_send = 0.0
    fps, t_prev = 0.0, time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                send(b"D")          
                time.sleep(0.1)
                continue

            raw = frame.copy()      
            dets = detector.detect(frame)
            frame_level, best_od, best_ow = SAFE, 0.0, 0.0
            boxes = []
            for x1, y1, x2, y2, conf in dets:
                lvl, od, ow = classify_hand((x1, y1, x2, y2), masks, frame.shape)
                frame_level = max(frame_level, lvl)
                best_od, best_ow = max(best_od, od), max(best_ow, ow)
                boxes.append((x1, y1, x2, y2, conf, lvl))

            now = time.time()
            for lvl in (WARNING, DANGER):
                cnt[lvl] = cnt[lvl] + 1 if frame_level >= lvl else 0
                if cnt[lvl] >= CONFIRM_FRAMES:
                    last_seen[lvl] = now
            if now - last_seen[DANGER] < HOLD_DANGER_SEC:
                state = DANGER
            elif now - last_seen[WARNING] < HOLD_WARNING_SEC:
                state = WARNING
            else:
                state = SAFE

            if now - last_send >= SEND_INTERVAL:     
                send(CODE[state])
                last_send = now
            if state != prev_state:
                log_event(events, state, len(dets))
                prev_state = state

            fps = 0.9 * fps + 0.1 * (1.0 / max(1e-6, now - t_prev))
            t_prev = now

            frame[any_zone] = (frame[any_zone] * 0.7 + layer[any_zone] * 0.3).astype(np.uint8)
            for key, lvl in (("warning", WARNING), ("danger", DANGER)):
                cv2.polylines(frame, [np.array(zones[key], np.int32)], True, BGR[lvl], 2)
            for x1, y1, x2, y2, conf, lvl in boxes:
                cv2.rectangle(frame, (x1, y1), (x2, y2), BGR[lvl], 2)
                cv2.putText(frame, f"hand {conf:.2f}", (x1, max(15, y1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, BGR[lvl], 1)
            info = (f"hands: {len(dets)} | in danger: {best_od:.2f} (need {MIN_OVERLAP_DANGER:.2f})"
                    f" | in warning: {best_ow:.2f} (need {MIN_OVERLAP_WARNING:.2f})")
            draw_ui(frame, state, fps, info, events)
            cv2.imshow("Hand monitoring", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key in (ord("z"), ord("r")):
                zones = setup_zones(raw, zones)
                masks, layer, any_zone = build_masks(zones, frame.shape)
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
