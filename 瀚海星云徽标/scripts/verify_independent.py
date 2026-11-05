import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".python-deps"))

import cv2
import numpy as np
from PIL import Image
from psd_tools import PSDImage

output = ROOT / "output"
preview = Image.open(output / "瀚海星云_预览.png")
assert preview.mode == "RGB", f"预览图颜色模式异常：{preview.mode}"
assert preview.size == (2048, 2048)
psd = PSDImage.open(output / "瀚海星云_源文件.psd")
assert psd.size == preview.size
assert psd.depth == 8
assert psd.color_mode.name == "RGB"
layers = list(psd.descendants())
text_layers = [layer for layer in layers if layer.kind == "type"]
shape_layers = [layer for layer in layers if layer.kind == "shape"]
assert len(text_layers) == 9
assert len(shape_layers) == 6
assert "".join(layer.text.rstrip("\x00") for layer in text_layers) == "中国科大瀚海星云研"
composite = psd.topil().convert("RGB")
assert np.array_equal(np.array(composite), np.array(preview)), "独立读取的 PSD 合成图与 PNG 不同。"

flower = next(layer for layer in layers if layer.name == "梅花形轮廓")
flower_alpha = np.zeros((2048, 2048), dtype=np.uint8)
flower_pixels = np.array(flower.topil().getchannel("A"))
flower_alpha[flower.top:flower.bottom, flower.left:flower.right] = flower_pixels
geometry = json.loads((ROOT / "work" / "geometry.json").read_text(encoding="utf-8"))
layout = json.loads((ROOT / "work" / "layout.json").read_text(encoding="utf-8"))
source_mask = 255 - np.array(Image.open(ROOT / "work" / "flower-mask.png"))
matrix = np.array([[layout["scale"], 0, layout["offset"][0]], [0, layout["scale"], layout["offset"][1]]])
target_mask = cv2.warpAffine(source_mask, matrix, (2048, 2048), flags=cv2.INTER_LINEAR)
target = target_mask > 127
actual = flower_alpha > 127
intersection = int(np.count_nonzero(target & actual))
union = int(np.count_nonzero(target | actual))
iou = intersection / union
assert iou > 0.985, f"梅花轮廓与参考图的重合度不足：{iou}"
distance_to_flower = cv2.distanceTransform(np.uint8(~actual), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
ring_clearance = 2048.0
for layer in text_layers[:8]:
    pixels = np.array(layer.topil().getchannel("A")) > 31
    distances = distance_to_flower[layer.top:layer.bottom, layer.left:layer.right]
    ring_clearance = min(ring_clearance, float(distances[pixels].min()))
assert ring_clearance >= 8, f"外圈文字与梅花轮廓间距不足：{ring_clearance}"
report = {
    "reader": "psd-tools",
    "previewMode": preview.mode,
    "size": list(preview.size),
    "textLayerCount": len(text_layers),
    "shapeLayerCount": len(shape_layers),
    "compositePixelsEqual": True,
    "flowerContourIoU": iou,
    "minimumTextFlowerClearancePixels": ring_clearance,
    "photoshopApplicationVerified": False,
}
(ROOT / "work" / "independent-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
