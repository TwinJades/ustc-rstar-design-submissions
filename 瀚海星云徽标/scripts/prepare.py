import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".python-deps"))

import cv2
import numpy as np
from PIL import Image

image = np.array(Image.open(ROOT / "assets" / "P1-reference.png").convert("RGB"))
height, width = image.shape[:2]
mask = ((image[:, :, 0] < 128) & (image[:, :, 1] < 190) & (image[:, :, 2] > 120)).astype(np.uint8)
colors, counts = np.unique(image[mask.astype(bool)], axis=0, return_counts=True)
blue = colors[counts.argmax()].tolist()
component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
flower_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
flower_component = np.uint8(labels == flower_label) * 255
flower_contours, _ = cv2.findContours(flower_component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
assert len(flower_contours) == 1, "梅花轮廓必须只有一个外轮廓。"
flower_contour = flower_contours[0]
flower_bounds = cv2.boundingRect(flower_contour)
assert 180 < flower_bounds[2] < 230 and 180 < flower_bounds[3] < 230, flower_bounds
flower_filled = np.zeros((height, width), dtype=np.uint8)
cv2.drawContours(flower_filled, [flower_contour], -1, 255, cv2.FILLED)
Image.fromarray(255 - flower_filled).save(ROOT / "work" / "flower-mask.png")

contours, hierarchy = cv2.findContours(mask * 255, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
circles = []
for index, contour in enumerate(contours):
    if len(contour) < 100:
        continue
    (cx, cy), (diameter_a, diameter_b), angle = cv2.fitEllipse(contour)
    radius = (diameter_a + diameter_b) / 4
    radii = np.linalg.norm(contour[:, 0, :] - np.array([cx, cy]), axis=1)
    if 70 < radius < 160 and abs(diameter_a - diameter_b) < 1.5 and radii.std() < 0.7:
        circles.append({"index": index, "center": [cx, cy], "radius": radius, "radialStd": float(radii.std()), "hierarchy": hierarchy[0, index].tolist()})
circles.sort(key=lambda item: item["radius"], reverse=True)
assert len(circles) == 5, f"校徽圆环边界数量异常：{len(circles)}"
geometry = {
    "width": width,
    "height": height,
    "blue": blue,
    "circles": circles,
    "flowerBounds": list(flower_bounds),
    "flowerCentroid": centroids[flower_label].tolist(),
    "flowerArea": int(np.count_nonzero(flower_filled)),
    "flowerContour": flower_contour[:, 0, :].tolist(),
}
(ROOT / "work" / "geometry.json").write_text(json.dumps(geometry, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in geometry.items() if key != "flowerContour"}, ensure_ascii=False, indent=2))
