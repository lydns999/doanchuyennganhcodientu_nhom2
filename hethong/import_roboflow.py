import argparse
import shutil
import sys
from pathlib import Path

import yaml

DEST = Path("dataset")
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLIT_MAP = {"train": "train", "valid": "val", "val": "val", "test": "train"}


def load_names(root):
    cfg = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))
    names = cfg.get("names", [])
    if isinstance(names, dict):
        names = [names[k] for k in sorted(names)]
    return [str(n) for n in names]


def convert_line(parts, keep_ids):
    """Return a YOLO box line with class 0, or None if the class is dropped."""
    cls = int(float(parts[0]))
    if keep_ids is not None and cls not in keep_ids:
        return None
    vals = [float(v) for v in parts[1:]]
    if len(vals) == 4:
        xc, yc, w, h = vals
    elif len(vals) >= 6 and len(vals) % 2 == 0:          
        xs, ys = vals[0::2], vals[1::2]
        x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
        xc, yc, w, h = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
    else:
        return None
    if w <= 0 or h <= 0:
        return None
    return f"0 {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="extracted Roboflow export folder")
    ap.add_argument("--all", action="store_true", help="treat every class as 'hand'")
    ap.add_argument("--prefix", default="rf", help="filename prefix (avoid clashes)")
    args = ap.parse_args()

    root = Path(args.folder)
    if not (root / "data.yaml").exists():
        sys.exit(f"data.yaml not found in {root}")

    names = load_names(root)
    print("Classes in dataset:", names)
    if args.all:
        keep_ids = None
    else:
        keep_ids = {i for i, n in enumerate(names) if "hand" in n.lower()}
        if not keep_ids:
            sys.exit("No class name contains 'hand'. Re-run with --all if every class is a hand/gesture.")
        print("Keeping classes:", [names[i] for i in sorted(keep_ids)])

    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (DEST / sub).mkdir(parents=True, exist_ok=True)

    total = {"train": 0, "val": 0}
    boxes = 0
    for split_dir, target in SPLIT_MAP.items():
        img_dir, lbl_dir = root / split_dir / "images", root / split_dir / "labels"
        if not img_dir.exists():
            continue
        for img in sorted(img_dir.iterdir()):
            if img.suffix.lower() not in IMG_EXT:
                continue
            new_name = f"{args.prefix}_{split_dir}_{img.name}"
            lines = []
            lbl = lbl_dir / (img.stem + ".txt")
            if lbl.exists():
                for raw in lbl.read_text().splitlines():
                    parts = raw.split()
                    if len(parts) < 5:
                        continue
                    out = convert_line(parts, keep_ids)
                    if out:
                        lines.append(out)
            shutil.copy2(img, DEST / "images" / target / new_name)
            (DEST / "labels" / target / (Path(new_name).stem + ".txt")).write_text(
                "\n".join(lines), encoding="utf-8")   
            total[target] += 1
            boxes += len(lines)

    print(f"Imported: train={total['train']}  val={total['val']}  hand boxes={boxes}")
    if total["val"] == 0:
        print("WARNING: no validation images. Put ~20 % of images/labels into dataset/*/val.")


if __name__ == "__main__":
    main()
