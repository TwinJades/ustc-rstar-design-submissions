import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".work" / "pythonlibs"))

import cv2
import numpy as np
from PIL import Image
from psd_tools import PSDImage
from psd_tools.constants import ColorMode, Resource

SIZE = (2048, 2048)
SCALE = 2048 / 1254
WORK = ROOT / ".work"
WORK.mkdir(exist_ok=True)
white = Image.open(ROOT / "科小牛科研助手_白色背景.png")
transparent = Image.open(ROOT / "科小牛科研助手_透明背景.png")
psd = PSDImage.open(ROOT / "科小牛科研助手.psd")
assert white.size == transparent.size == psd.size == SIZE
assert white.mode == "RGB" and transparent.mode == "RGBA"
assert psd.color_mode == ColorMode.RGB
assert white.info["icc_profile"] == transparent.info["icc_profile"]
assert Resource.ICC_PROFILE in psd.image_resources
assert len(psd) == 13
assert len({layer.name for layer in psd}) == 13
assert all(layer.kind == "pixel" and layer.has_pixels() for layer in psd)
assert all(not layer.has_mask() for layer in psd)
assert all(layer.visible and layer.opacity == 255 for layer in psd)


def canvas(layer):
    result = Image.new("RGBA", SIZE)
    result.alpha_composite(layer.topil().convert("RGBA"), (layer.left, layer.top))
    return result


def source_roi(array, box):
    x0, y0, x1, y1 = [round(value * SCALE) for value in box]
    return array[y0:y1, x0:x1]


layers = {layer.name: layer for layer in psd}
alpha = np.array(transparent)[:, :, 3]
assert alpha[0].max() == alpha[-1].max() == alpha[:, 0].max() == alpha[:, -1].max() == 0
foreground = alpha > 128
count, labels, stats, centers = cv2.connectedComponentsWithStats(foreground.astype(np.uint8))
areas = sorted(stats[1:, cv2.CC_STAT_AREA], reverse=True)
assert areas[0] / sum(areas) > 0.999

# 强制从图层重新合成，避免使用文件里的缓存预览。
rendered = psd.composite(force=True, apply_icc=False).convert("RGB")
diff_white = np.abs(np.array(rendered).astype(np.int16) - np.array(white).astype(np.int16))
assert diff_white.max() <= 2, int(diff_white.max())
merged = Image.open(ROOT / "科小牛科研助手.psd").convert("RGB")
diff_merged = np.abs(np.array(merged).astype(np.int16) - np.array(white).astype(np.int16))
assert diff_merged.max() <= 2
psd[0].visible = False
rendered_alpha = psd.composite(force=True, apply_icc=False).convert("RGBA")
diff_alpha = np.abs(np.array(rendered_alpha).astype(np.int16) - np.array(transparent).astype(np.int16))
assert diff_alpha[:, :, 3].max() <= 2
visible_pixels = np.array(transparent)[:, :, 3] > 250
assert diff_alpha[:, :, :3][visible_pixels].max() <= 2
psd[0].visible = True

head = np.array(canvas(layers["头部_完整脸部底图"]))
for box in [(470, 350, 548, 470), (700, 350, 779, 470), (560, 630, 690, 675)]:
    region = source_roi(head, box)
    assert region[:, :, 3].min() >= 250
    assert region[:, :, :3].min() > 100
head_rgb = source_roi(head, (540, 625, 710, 684))[:, :, :3].astype(int)
assert np.sum(head_rgb[:, :, 0] - head_rgb[:, :, 1] > 25) < 10

coat = np.array(canvas(layers["白大褂_翻领纽扣与双口袋"]))
chest = source_roi(coat, (665, 868, 775, 908)).astype(int)
assert chest[:, :, 3].min() >= 250
assert np.sum(chest[:, :, 2] - chest[:, :, 0] > 50) == 0
letter_image = np.array(canvas(layers["左胸_USTC"])).astype(int)
letter_pixels = ((letter_image[:, :, 2] - letter_image[:, :, 0] > 50) & (letter_image[:, :, 3] > 128)).astype(np.uint8)
letter_count, letter_labels, letter_stats, letter_centers = cv2.connectedComponentsWithStats(letter_pixels)
assert sum(area > 100 for area in letter_stats[1:, cv2.CC_STAT_AREA]) == 4
body = np.array(canvas(layers["身体完整底图"]))
assert source_roi(body, (540, 850, 720, 1040))[:, :, 3].min() >= 250

glasses = np.array(canvas(layers["黑色圆框眼镜"]))
for x, y in [(490, 400), (750, 400)]:
    assert source_roi(glasses, (x - 5, y - 5, x + 5, y + 5))[:, :, 3].max() == 0
glasses_mask = glasses[:, :, 3] > 128
contours, hierarchy = cv2.findContours(glasses_mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
holes = [abs(cv2.contourArea(contours[index])) for index, item in enumerate(hierarchy[0]) if item[3] >= 0]
assert sum(area > 10000 for area in holes) == 2

# 每个独立部件均实际参与最终画面，并能单独恢复原始位置。
independent_checks = []
for index, layer in enumerate(psd):
    if index == 0:
        continue
    standalone = canvas(layer)
    assert standalone.getbbox() is not None
    rest = Image.new("RGBA", SIZE)
    for other_index, other in enumerate(psd):
        if other_index != index:
            rest = Image.alpha_composite(rest, canvas(other))
    change = np.max(np.abs(np.array(rest.convert("RGB")).astype(np.int16) - np.array(white).astype(np.int16)), axis=2)
    changed = int(np.sum(change > 5))
    if layer.name != "身体完整底图":
        assert changed > 100, layer.name
    independent_checks.append({"图层": layer.name, "隐藏后变化像素": changed})

editable_copy = PSDImage.open(ROOT / "科小牛科研助手.psd")
editable_glasses = next(layer for layer in editable_copy if layer.name == "黑色圆框眼镜")
original_offset = editable_glasses.offset
original_glasses = np.array(editable_glasses.topil())
editable_glasses.offset = (original_offset[0] + 64, original_offset[1] + 32)
editable_path = WORK / "移动图层检查.psd"
editable_copy.save(editable_path)
reopened = PSDImage.open(editable_path)
moved_glasses = next(layer for layer in reopened if layer.name == "黑色圆框眼镜")
assert moved_glasses.offset == (original_offset[0] + 64, original_offset[1] + 32)
assert np.array_equal(np.array(moved_glasses.topil()), original_glasses)

source = Image.open(ROOT / "制作素材" / "形象生成原图.png").convert("RGBA").resize(SIZE, Image.Resampling.LANCZOS)
source_alpha = np.array(source)[:, :, 3] > 128
intersection = np.sum(source_alpha & foreground)
union = np.sum(source_alpha | foreground)
silhouette_iou = float(intersection / union)
assert silhouette_iou > 0.98, silhouette_iou

report = {
    "检查结果": "通过",
    "尺寸": list(SIZE),
    "白色背景模式": white.mode,
    "透明背景模式": transparent.mode,
    "PSD图层数量": len(psd),
    "PSD强制合成与白色PNG最大通道差值": int(diff_white.max()),
    "PSD强制合成与透明PNG最大透明度差值": int(diff_alpha[:, :, 3].max()),
    "Pillow读取PSD合并预览与白色PNG最大通道差值": int(diff_merged.max()),
    "图层移动保存检查": "眼镜平移后保存并重新打开，坐标变化正确且图层像素保持完整",
    "合成形象与生成形象轮廓重合率": silhouette_iou,
    "头部底图": "隐藏眼睛、眼镜与嘴巴后，脸部保持完整且没有重复内容",
    "白大褂底图": "隐藏文字后没有重复字样",
    "身体底图": "白大褂后方保留完整身体",
    "眼镜": "两个镜片内部透明",
    "独立图层检查": independent_checks,
    "软件检查范围": "使用psd-tools重新打开及强制合成；未在Photoshop或PhotoCraft桌面程序中打开",
}
(ROOT / "制作素材" / "文件检查结果.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
