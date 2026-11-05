const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const { createCanvas, loadImage } = require('canvas');
require('ag-psd/initialize-canvas');
const { readPsd } = require('ag-psd');

const ROOT = path.resolve(__dirname, '..');
const WORK = path.join(ROOT, 'work');
const OUT = path.join(ROOT, 'output');
const layout = JSON.parse(fs.readFileSync(path.join(WORK, 'layout.json'), 'utf8'));
const N = layout.size;
const psd = readPsd(fs.readFileSync(path.join(OUT, '瀚海星云_源文件.psd')), {
  useImageData: true, skipThumbnail: true, throwForMissingFeatures: true,
});
assert.equal(psd.width, N);
assert.equal(psd.height, N);
assert.equal(psd.colorMode, 3);
assert.equal(psd.bitsPerChannel, 8);
assert.equal(psd.channels, 3);
const layers = [];
function collect(items) {
  for (const item of items) {
    if (item.children) collect(item.children);
    else layers.push(item);
  }
}
collect(psd.children);
const textLayers = layers.filter(layer => layer.text);
const shapeLayers = layers.filter(layer => layer.vectorMask);
assert.equal(textLayers.length, 9);
assert.equal(shapeLayers.length, 6);
assert.equal(textLayers.map(layer => layer.text.text).join(''), '中国科大瀚海星云研');
assert.equal(layers.filter(layer => !layer.text && !layer.vectorMask).length, 0);
for (const layer of textLayers) {
  const expectedFont = layout.fonts.chinese;
  assert.equal(layer.text.style.font.name, expectedFont);
  assert(layer.text.style.fontSize > 0);
  assert.equal(layer.text.transform.length, 6);
  assert(layer.text.transform.every(Number.isFinite));
}
for (const layer of shapeLayers) {
  assert.equal(layer.vectorFill.type, 'color');
  assert(layer.vectorMask.paths.length > 0);
  for (const contour of layer.vectorMask.paths) {
    assert(!contour.open);
    assert(contour.knots.length >= 4);
    assert(contour.knots.every(knot => knot.points.length === 6 && knot.points.every(Number.isFinite)));
  }
}
for (let i = 0; i < 8; i++) {
  const actual = textLayers[i].text.transform;
  const expected = layout.glyphMetrics[i].transform;
  assert(actual.every((value, j) => Math.abs(value - expected[j]) < 1e-7));
}

function alphaAt(layer, x, y) {
  x -= layer.left; y -= layer.top;
  if (x < 0 || y < 0 || x >= layer.imageData.width || y >= layer.imageData.height) return 0;
  return layer.imageData.data[(y * layer.imageData.width + x) * 4 + 3];
}
const flower = layers.find(layer => layer.name === '梅花形轮廓');
const occupied = new Uint8Array(N * N);
let ringOverlap = 0, flowerOverlap = 0;
let maximumRadius = 0, minimumRadius = N;
for (const layer of textLayers.slice(0, 8)) {
  assert(layer.bottom < N / 2, '外圈文字越过上半圈。');
  const { width, height, data } = layer.imageData;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    if (data[(y * width + x) * 4 + 3] < 32) continue;
    const px = layer.left + x, py = layer.top + y;
    assert(px > 0 && py > 0 && px < N - 1 && py < N - 1, '文字出现裁切。');
    const position = py * N + px;
    if (occupied[position]) ringOverlap++;
    occupied[position] = 1;
    if (alphaAt(flower, px, py) > 32) flowerOverlap++;
    const radius = Math.hypot(px - N / 2, py - N / 2);
    maximumRadius = Math.max(maximumRadius, radius);
    minimumRadius = Math.min(minimumRadius, radius);
  }
}
assert.equal(ringOverlap, 0, '外圈文字笔画之间存在重叠。');
assert.equal(flowerOverlap, 0, '外圈文字与梅花轮廓存在重叠。');
assert(maximumRadius < layout.radii[1] - 12, '文字距离外侧圆环过近。');
const central = textLayers[8];
let centralMaximumRadius = 0;
for (let y = 0; y < central.imageData.height; y++) for (let x = 0; x < central.imageData.width; x++) {
  if (central.imageData.data[(y * central.imageData.width + x) * 4 + 3] < 32) continue;
  centralMaximumRadius = Math.max(centralMaximumRadius,
    Math.hypot(central.left + x - N / 2, central.top + y - N / 2));
}
assert(centralMaximumRadius < layout.diskRadius - 20, '中央文字距离圆盘边缘过近。');

async function main() {
  const preview = await loadImage(fs.readFileSync(path.join(OUT, '瀚海星云_预览.png')));
  assert.equal(preview.width, N);
  assert.equal(preview.height, N);
  const previewCanvas = createCanvas(N, N);
  previewCanvas.getContext('2d').drawImage(preview, 0, 0);
  const previewData = previewCanvas.getContext('2d').getImageData(0, 0, N, N).data;
  let compositeDifferences = 0;
  for (let i = 0; i < previewData.length; i++) {
    if (previewData[i] !== psd.imageData.data[i]) compositeDifferences++;
  }
  assert.equal(compositeDifferences, 0, 'PSD 合成图与 PNG 像素存在差异。');
  const recomposed = createCanvas(N, N);
  const ctx = recomposed.getContext('2d');
  function compose(items) {
    for (const layer of items.toReversed()) {
      if (layer.children) compose(layer.children);
      else {
        const canvas = createCanvas(layer.imageData.width, layer.imageData.height);
        canvas.getContext('2d').putImageData(layer.imageData, 0, 0);
        ctx.drawImage(canvas, layer.left, layer.top);
      }
    }
  }
  compose(psd.children);
  const recomposedData = ctx.getImageData(0, 0, N, N).data;
  let layerCompositeDifferences = 0;
  for (let i = 0; i < previewData.length; i++) if (previewData[i] !== recomposedData[i]) layerCompositeDifferences++;
  assert.equal(layerCompositeDifferences, 0, '读取后的分层合成与 PNG 像素存在差异。');
  let lowerAnnulusPixels = 0;
  const innerRadius = 110 * layout.scale;
  const outerRadius = layout.radii[1] - 4;
  for (let y = N / 2; y < N; y++) for (let x = 0; x < N; x++) {
    const radius = Math.hypot(x - N / 2, y - N / 2);
    if (radius > innerRadius && radius < outerRadius) {
      const index = (y * N + x) * 4;
      assert(previewData[index] === 255 && previewData[index + 1] === 255 && previewData[index + 2] === 255,
        '下半圈文字区域出现额外内容。');
      lowerAnnulusPixels++;
    }
  }
  const report = {
    size: [N, N], colorMode: 'RGB', bitsPerChannel: 8,
    textLayers: textLayers.map(layer => ({ name: layer.name, text: layer.text.text,
      font: layer.text.style.font.name, fontSize: layer.text.style.fontSize })),
    shapeLayers: shapeLayers.map(layer => ({ name: layer.name, paths: layer.vectorMask.paths.length,
      nodes: layer.vectorMask.paths.reduce((sum, contour) => sum + contour.knots.length, 0) })),
    ringOverlap, flowerOverlap, maximumRadius, minimumRadius, centralMaximumRadius,
    outerRingClearance: layout.radii[1] - maximumRadius,
    centralDiskClearance: layout.diskRadius - centralMaximumRadius,
    compositeDifferences, layerCompositeDifferences, lowerAnnulusPixels,
    photoshopApplicationVerified: false,
  };
  fs.writeFileSync(path.join(WORK, 'verification.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}
main();
