from pathlib import Path

from ultralytics import YOLO

DATASET = Path("dataset").resolve()
EPOCHS = 100
IMGSZ = 640
BATCH = 16          
BASE_MODEL = "yolov8n.pt"


def write_data_yaml():
    yaml_path = DATASET / "data.yaml"
    yaml_path.write_text(
        f"path: {DATASET.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        "  0: hand\n",
        encoding="utf-8",
    )
    return yaml_path


def main():
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        if not (DATASET / sub).exists():
            raise SystemExit(f"Missing folder: {DATASET / sub}")

    data_yaml = write_data_yaml()
    model = YOLO(BASE_MODEL)  
    model.train(
        data=str(data_yaml),
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=BATCH,
        device=0,
        workers=2,
        patience=25,        
        name="hand",
        exist_ok=True,

        degrees=10,
        translate=0.1,
        scale=0.4,
        fliplr=0.5,
        hsv_v=0.4,          
        mosaic=1.0,
    )
    metrics = model.val()
    print("mAP50:", metrics.box.map50, " mAP50-95:", metrics.box.map)
    print("Best weights: runs/detect/hand/weights/best.pt")


if __name__ == "__main__":   
    main()
