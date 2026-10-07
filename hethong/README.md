
## 1. Tải (Python 3.11, in the venv)

python -m pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 --no-cache-dir
pip install -r requirements.txt
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"   (must print +cu... True)

Có CUDA thì train nhanh hơn

## 2. Build dataset

## 3. Train

python train_hand.py

## 4. Test camera + model

python danger_zone_hand.py

## 5. ESP32 + PLC
1. esp32_plc_bridge.ino
2.USE_SERIAL = True
