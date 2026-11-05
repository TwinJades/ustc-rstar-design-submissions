import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".work" / "pythonlibs"))

import cv2
import numpy as np
from PIL import Image, ImageCms, ImageDraw, ImageFilter
from psd_tools import PSDImage
from psd_tools.constants import Resource
from psd_tools.psd.image_resources import ImageResource

ASSETS = ROOT / "制作素材"
PARTS = ASSETS / "独立部件"
PARTS.mkdir(exist_ok=True)
SIZE = (2048, 2048)
ICC = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def load_clean(name):
    image = np.array(Image.open(ASSETS / name).convert("RGBA"))
    count, labels, stats, centers = cv2.connectedComponentsWithStats(
        (image[:, :, 3] > 128).astype(np.uint8)
    )
    largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    support = cv2.dilate((labels == largest).astype(np.uint8), np.ones((3, 3), np.uint8))
    alpha = image[:, :, 3].astype(np.float32)
    alpha = np.where(alpha >= 235, 255, alpha)
    alpha = np.where((alpha < 40) | (support == 0), 0, alpha)
    image[:, :, 3] = alpha.astype(np.uint8)
    image[image[:, :, 3] == 0, :3] = 0
    return Image.fromarray(image)


original = load_clean("形象生成原图.png")
blank = load_clean("完整底图.png")
anatomy = load_clean("身体四肢底图.png")
assert original.size == blank.size == anatomy.size == (1254, 1254)
W, H = original.size
Y, X = np.mgrid[:H, :W]
raw = np.array(original)
bare = np.array(blank)


def polygon(points):
    mask = Image.new("L", (W, H))
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return np.array(mask) / 255.0


def rect(box):
    x0, y0, x1, y1 = box
    return ((X >= x0) & (X < x1) & (Y >= y0) & (Y < y1)).astype(float)


def part(image, mask):
    array = np.array(image).copy()
    array[:, :, 3] = np.rint(array[:, :, 3] * np.clip(mask, 0, 1)).astype(np.uint8)
    array[array[:, :, 3] == 0, :3] = 0
    return Image.fromarray(array)


def over(bottom, top):
    return Image.alpha_composite(bottom, top)


# 使用生成底图保留完整脸部，并依据鼻口区域的轮廓划分头部下缘。
white = ((np.min(bare[:, :, :3], axis=2) > 233) & (Y > 490) & (Y < 760)).astype(np.uint8)
count, labels, stats, centers = cv2.connectedComponentsWithStats(white)
muzzle_id = labels[600, 620]
assert muzzle_id != 0
muzzle = labels == muzzle_id
head_mask = Y < 700
expanded_muzzle = cv2.dilate(muzzle.astype(np.uint8), np.ones((27, 27), np.uint8))
head_mask = head_mask | (expanded_muzzle > 0)
head_mask &= Y < 765
head = part(blank, head_mask)

left_arm_region = polygon([(0, 735), (513, 735), (486, 806), (438, 967), (430, 1025), (0, 1025)])
right_arm_region = np.fliplr(left_arm_region)
body_region = polygon([(508, 742), (746, 742), (790, 944), (805, 1053), (778, 1098), (477, 1098), (448, 1053), (464, 944)])
body = part(anatomy, body_region * (Y >= 760))

# 肢体上端保留生成的延伸部分，外部保留原有袖口与蹄子。
left_arm_region *= Y >= 760
right_arm_region *= Y >= 760
left_arm = over(part(anatomy, left_arm_region), part(blank, left_arm_region))
right_arm = over(part(anatomy, right_arm_region), part(blank, right_arm_region))
left_leg_region = rect((430, 1045, 627, 1230))
right_leg_region = rect((627, 1045, 825, 1230))
left_leg = over(part(anatomy, left_leg_region), part(blank, left_leg_region * (Y >= 1100)))
right_leg = over(part(anatomy, right_leg_region), part(blank, right_leg_region * (Y >= 1100)))

# 白大褂图层与两侧袖子分别保存，遮挡关系通过普通图层顺序实现。
rgb = bare[:, :, :3].astype(np.int16)
coat_color = ((rgb[:, :, 0] - rgb[:, :, 2] < 27) & (np.min(rgb, axis=2) > 105)) | (
    rgb[:, :, 2] - rgb[:, :, 0] > 15
)
coat_mask = coat_color * rect((330, 741, 925, 1110)) * (1 - left_arm_region) * (1 - right_arm_region) * (1 - head_mask)
coat = part(blank, coat_mask)

dark = ((np.max(raw[:, :, :3], axis=2) < 115) * rect((350, 300, 900, 500))).astype(np.uint8)
count, labels, stats, centers = cv2.connectedComponentsWithStats(dark)
frame_id = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
assert stats[frame_id, cv2.CC_STAT_WIDTH] > 450
frame_mask = (labels == frame_id).astype(np.uint8)
frame_mask = cv2.GaussianBlur(frame_mask.astype(np.float32), (3, 3), 0.45)
glasses = part(original, frame_mask)

eye_area = Image.new("L", (W, H))
draw = ImageDraw.Draw(eye_area)
draw.ellipse((453, 332, 565, 480), fill=255)
draw.ellipse((686, 332, 798, 480), fill=255)
draw.rectangle((482, 277, 547, 303), fill=255)
draw.rectangle((707, 277, 774, 303), fill=255)
delta = np.max(np.abs(raw[:, :, :3].astype(float) - bare[:, :, :3].astype(float)), axis=2)
eye_mask = np.array(eye_area) / 255.0 * np.clip((delta - 5) / 10, 0, 1)
eye_mask *= 1 - cv2.dilate((labels == frame_id).astype(np.uint8), np.ones((3, 3), np.uint8))
left_eye = part(original, eye_mask * (X < 627))
right_eye = part(original, eye_mask * (X >= 627))

source_rgb = raw[:, :, :3].astype(float)
mouth_color = (source_rgb[:, :, 0] > source_rgb[:, :, 1] + 20) & (source_rgb[:, :, 1] > source_rgb[:, :, 2] + 5)
mouth_mask = mouth_color * rect((535, 622, 710, 686))
mouth_mask = cv2.GaussianBlur(mouth_mask.astype(np.float32), (3, 3), 0.45)
mouth = part(original, mouth_mask)
letter_color = np.clip((source_rgb[:, :, 2] - source_rgb[:, :, 0] - 8) / 45, 0, 1)
letter_mask = letter_color * rect((665, 867, 774, 907))
letters = part(original, letter_mask)

layers = [
    ("身体完整底图", body),
    ("右腿及蹄子", left_leg),
    ("左腿及蹄子", right_leg),
    ("右臂及袖子", left_arm),
    ("左臂及袖子", right_arm),
    ("白大褂_翻领纽扣与双口袋", coat),
    ("头部_完整脸部底图", head),
    ("右眼与眉毛", left_eye),
    ("左眼与眉毛", right_eye),
    ("嘴巴_微笑", mouth),
    ("黑色圆框眼镜", glasses),
    ("左胸_USTC", letters),
]

psd = PSDImage.new(mode="RGBA", size=SIZE, depth=8)
psd.image_resources[Resource.ICC_PROFILE] = ImageResource(key=Resource.ICC_PROFILE, data=ICC)
background = psd.create_pixel_layer(Image.new("RGB", SIZE, "white"), name="Background")
background.name = "白色背景"
composite = Image.new("RGBA", SIZE)
manifest = []
for name, image in layers:
    image = image.resize(SIZE, Image.Resampling.LANCZOS)
    assert image.getbbox() is not None, name
    image.save(PARTS / f"{name}.png", icc_profile=ICC)
    composite = over(composite, image)
    bbox = image.getbbox()
    layer = psd.create_pixel_layer(image.crop(bbox), name=f"Layer{len(manifest) + 1:02d}", left=bbox[0], top=bbox[1])
    layer.name = name
    manifest.append({"name": name, "bbox": list(bbox)})

composite.save(ROOT / "科小牛科研助手_透明背景.png", icc_profile=ICC)
white_preview = over(Image.new("RGBA", SIZE, "white"), composite).convert("RGB")
white_preview.save(ROOT / "科小牛科研助手_白色背景.png", icc_profile=ICC)
psd.save(ROOT / "科小牛科研助手.psd")

manifest_path = ASSETS / "图层清单.json"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"psd": str(ROOT / "科小牛科研助手.psd"), "layers": len(psd), "size": SIZE, "parts": len(layers)}, ensure_ascii=False))
