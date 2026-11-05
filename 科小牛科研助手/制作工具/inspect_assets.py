import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".work" / "pythonlibs"))

import cv2
import numpy as np
from PIL import Image

image = np.array(Image.open(ROOT / "制作素材" / "形象生成原图.png"))
foreground = (image[:, :, 3] > 128).astype(np.uint8)
count, labels, stats, centers = cv2.connectedComponentsWithStats(foreground)
print("foreground", sorted(stats[1:].tolist(), key=lambda item: item[4], reverse=True)[:4])
mask = (np.max(image[:, :, :3], axis=2) < 115).astype(np.uint8)
mask[:250] = 0
mask[510:] = 0
mask[:, :300] = 0
mask[:, 950:] = 0
count, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
print("dark", sorted(stats[1:].tolist(), key=lambda item: item[4], reverse=True)[:12])
print("versions", cv2.__version__)
