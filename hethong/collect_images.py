"""
  SPACE = save 
  a     = autosave 
  q     = quit
"""
import time
from pathlib import Path

import cv2

CAM_INDEX = 1            
FRAME_W, FRAME_H = 640, 480
OUT_DIR = Path("dataset_raw")
AUTO_INTERVAL = 0.6      


def main():
    OUT_DIR.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

    count = len(list(OUT_DIR.glob("*.jpg")))
    auto = False
    last = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Cannot read camera")
            break

        view = frame.copy()
        cv2.putText(view, f"saved: {count}  auto: {'ON' if auto else 'OFF'}",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.imshow("collect", view)

        now = time.time()
        key = cv2.waitKey(1) & 0xFF
        save = False
        if key == ord(" "):
            save = True
        elif key == ord("a"):
            auto = not auto
        elif key == ord("q"):
            break
        if auto and now - last >= AUTO_INTERVAL:
            save = True

        if save:
            name = OUT_DIR / f"img_{int(now * 1000)}.jpg"
            cv2.imwrite(str(name), frame)
            count += 1
            last = now

    cap.release()
    cv2.destroyAllWindows()
    print(f"Done. {count} images in {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
