const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const { createCanvas } = require('canvas');
require('ag-psd/initialize-canvas');
const { writePsdBuffer } = require('ag-psd');
const opentype = require('opentype.js');
const vtracer = require('@visioncortex/vtracer');
const svgpath = require('svgpath');
const { XMLParser } = require('fast-xml-parser');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'output');
const WORK = path.join(ROOT, 'work');
const N = 2048;
const geometry = JSON.parse(fs.readFileSync(path.join(WORK, 'geometry.json'), 'utf8'));
const scale = N / geometry.width;
const sourceCenter = geometry.circles[0].center;
const offset = [N / 2 - sourceCenter[0] * scale, N / 2 - sourceCenter[1] * scale];
const center = [N / 2, N / 2];
const blue = { r: geometry.blue[0], g: geometry.blue[1], b: geometry.blue[2] };
const white = { r: 255, g: 255, b: 255 };
const chinesePath = path.join(ROOT, 'assets', 'fonts', 'ZhiMangXing-Regular.ttf');
const fonts = { chinese: opentype.loadSync(chinesePath) };
const fontNames = { chinese: 'ZhiMangXing-Regular' };
for (const character of '中国科大瀚海星云研') {
  assert(fonts.chinese.charToGlyphIndex(character) > 0, `字体缺少字形：${character}`);
}

function css(color) { return `rgb(${color.r},${color.g},${color.b})`; }
function knot(x, y, incoming = [x, y], outgoing = [x, y]) {
  return { linked: false, points: [...incoming, x, y, ...outgoing] };
}
function circle(radius, operation = 'combine') {
  const [x, y] = center;
  const k = radius * 0.5522847498307936;
  return { open: false, operation, fillRule: 'even-odd', knots: [
    knot(x, y - radius, [x - k, y - radius], [x + k, y - radius]),
    knot(x + radius, y, [x + radius, y - k], [x + radius, y + k]),
    knot(x, y + radius, [x + k, y + radius], [x - k, y + radius]),
    knot(x - radius, y, [x - radius, y + k], [x - radius, y - k]),
  ] };
}
function drawPaths(ctx, paths) {
  ctx.beginPath();
  for (const contour of paths) {
    const nodes = contour.knots;
    ctx.moveTo(nodes[0].points[2], nodes[0].points[3]);
    for (let i = 0; i < nodes.length; i++) {
      const p = nodes[i].points;
      const q = nodes[(i + 1) % nodes.length].points;
      ctx.bezierCurveTo(p[4], p[5], q[0], q[1], q[2], q[3]);
    }
    ctx.closePath();
  }
  ctx.fill('evenodd');
}
function alphaBounds(canvas) {
  const data = canvas.getContext('2d').getImageData(0, 0, N, N).data;
  let x0 = N, y0 = N, x1 = -1, y1 = -1;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    if (data[(y * N + x) * 4 + 3] > 0) {
      x0 = Math.min(x0, x); y0 = Math.min(y0, y);
      x1 = Math.max(x1, x); y1 = Math.max(y1, y);
    }
  }
  assert(x1 >= x0 && y1 >= y0, '图层没有有效像素。');
  return { left: x0, top: y0, right: x1 + 1, bottom: y1 + 1 };
}
function cropped(canvas, name, extra) {
  const bounds = alphaBounds(canvas);
  const imageData = canvas.getContext('2d').getImageData(bounds.left, bounds.top,
    bounds.right - bounds.left, bounds.bottom - bounds.top);
  return { name, ...bounds, imageData, blendMode: 'normal', opacity: 1, ...extra };
}
function shape(name, paths, color) {
  const canvas = createCanvas(N, N);
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = css(color);
  drawPaths(ctx, paths);
  return cropped(canvas, name, {
    vectorMask: { fillStartsWithAllPixels: false, paths },
    vectorFill: { type: 'color', color },
    vectorStroke: { fillEnabled: true, strokeEnabled: false },
  });
}

// 使用库解析 SVG，再将曲线节点转换为 PSD 的 Bézier 节点。
function svgToBezier(data, transform) {
  const parsed = svgpath(data).transform(transform).translate(-0.5, -0.5).scale(scale).translate(...offset)
    .abs().unshort().unarc();
  assert.equal(parsed.err, '');
  const curves = [];
  let nodes;
  parsed.iterate((segment) => {
    const command = segment[0];
    if (command === 'M') {
      nodes = [knot(segment[1], segment[2])];
      curves.push({ open: false, operation: 'combine', fillRule: 'even-odd', knots: nodes });
    } else if (command === 'C') {
      const previous = nodes[nodes.length - 1].points;
      previous[4] = segment[1]; previous[5] = segment[2];
      nodes.push(knot(segment[5], segment[6], [segment[3], segment[4]]));
    } else if (command === 'L') {
      nodes.push(knot(segment[1], segment[2]));
    } else if (command === 'Z') {
      const first = nodes[0].points;
      const last = nodes[nodes.length - 1].points;
      if (Math.hypot(first[2] - last[2], first[3] - last[3]) < 0.01) {
        first[0] = last[0]; first[1] = last[1]; nodes.pop();
      }
    } else {
      throw new Error(`轮廓中出现不支持的曲线节点：${command}`);
    }
  });
  return curves;
}
const flowerSvg = vtracer.convertBuffer(fs.readFileSync(path.join(WORK, 'flower-mask.png')), {
  clustering: 'bw', mode: 'spline', filterSpeckle: 4, simplify: 0.45, pathPrecision: 4,
});
fs.writeFileSync(path.join(WORK, 'flower-outline.svg'), flowerSvg);
const xml = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: '' }).parse(flowerSvg);
const sourcePaths = Array.isArray(xml.svg.path) ? xml.svg.path : [xml.svg.path];
assert.equal(sourcePaths.length, 1, '梅花轮廓必须是一个独立路径。');
const flowerPaths = svgToBezier(sourcePaths[0].d, sourcePaths[0].transform || 'translate(0,0)');

const radii = geometry.circles.map((item, index) =>
  (item.radius + ([0, 3].includes(index) ? 0.5 : -0.5)) * scale);
const innerWhiteBand = radii[2] - radii[3];
const diskRadius = radii[4] - innerWhiteBand;
assert(diskRadius > 450 && diskRadius < 500);
const structuralLayers = [
  shape('外侧圆环', [circle(radii[0]), circle(radii[1], 'subtract')], blue),
  shape('梅花形轮廓', flowerPaths, blue),
  shape('内部双圆环 · 外侧白色间隔', [circle(radii[2])], white),
  shape('内部双圆环 · 蓝色圆环', [circle(radii[3]), circle(radii[4], 'subtract')], blue),
  shape('中央蓝色圆盘', [circle(diskRadius)], blue),
];

function glyphLayer(character, kind, size, transform, color, name) {
  const font = fonts[kind];
  const glyph = font.charToGlyph(character);
  const outline = glyph.getPath(0, 0, size);
  outline.fill = css(color);
  const canvas = createCanvas(N, N);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(...transform);
  outline.draw(ctx);
  const box = outline.getBoundingBox();
  return cropped(canvas, name, {
    text: {
      text: character, transform, orientation: 'horizontal', antiAlias: 'smooth',
      shapeType: 'point', pointBase: [0, 0],
      style: { font: { name: fontNames[kind] }, fontSize: size, fillColor: color, autoKerning: false },
      paragraphStyle: { justification: 'left' },
      bounds: {
        left: { units: 'Pixels', value: box.x1 }, top: { units: 'Pixels', value: box.y1 },
        right: { units: 'Pixels', value: box.x2 }, bottom: { units: 'Pixels', value: box.y2 },
      },
    },
  });
}

// 按实际墨迹边界居中，避免字体自带留白影响位置。
const ringCharacters = Array.from('中国科大瀚海星云');
const ringFontSize = 29.5 * scale;
const ringRadius = 121.5 * scale;
const span = 145 * Math.PI / 180;
const gap = 6 * Math.PI / 180;
const spacing = (span - gap) / (ringCharacters.length - 1);
const ringLayers = [];
const glyphMetrics = [];
for (let i = 0; i < ringCharacters.length; i++) {
  const character = ringCharacters[i];
  const kind = 'chinese';
  const size = ringFontSize;
  const box = fonts[kind].charToGlyph(character).getPath(0, 0, size).getBoundingBox();
  const angle = -span / 2 + i * spacing + (i >= 4 ? gap : 0);
  const rotation = angle;
  const cos = Math.cos(rotation), sin = Math.sin(rotation);
  const middleX = (box.x1 + box.x2) / 2, middleY = (box.y1 + box.y2) / 2;
  const x = center[0] + ringRadius * Math.sin(angle);
  const y = center[1] - ringRadius * Math.cos(angle);
  const transform = [cos, sin, -sin, cos,
    x - cos * middleX + sin * middleY, y - sin * middleX - cos * middleY];
  const layer = glyphLayer(character, kind, size, transform, blue, `外圈文字 ${i + 1} · ${character}`);
  ringLayers.push(layer);
  glyphMetrics.push({ character, kind, size, angle, center: [x, y], transform, bounds: {
    left: layer.left, top: layer.top, right: layer.right, bottom: layer.bottom,
  } });
}
const centralGlyph = fonts.chinese.charToGlyph('研');
const normalizedBox = centralGlyph.getPath(0, 0, 1000).getBoundingBox();
const centralSize = diskRadius * 1.48 * 1000 / Math.max(normalizedBox.x2 - normalizedBox.x1,
  normalizedBox.y2 - normalizedBox.y1);
const centralBox = centralGlyph.getPath(0, 0, centralSize).getBoundingBox();
const centralTransform = [1, 0, 0, 1,
  center[0] - (centralBox.x1 + centralBox.x2) / 2,
  center[1] - (centralBox.y1 + centralBox.y2) / 2];
const centralLayer = glyphLayer('研', 'chinese', centralSize, centralTransform, white, '中央行书 · 研');
const background = shape('白色背景', [{ open: false, operation: 'combine', fillRule: 'even-odd',
  knots: [knot(0, 0), knot(N, 0), knot(N, N), knot(0, N)] }], white);

const children = [
  { name: '上半圈文字 · 中国科大 瀚海星云', opened: true, children: ringLayers },
  centralLayer,
  { name: '校徽结构', opened: true, children: structuralLayers.toReversed() },
  background,
];
const composite = createCanvas(N, N);
const compositeContext = composite.getContext('2d', { alpha: false });
function compose(layers) {
  for (const layer of layers.toReversed()) {
    if (layer.children) compose(layer.children);
    else {
      const canvas = createCanvas(layer.imageData.width, layer.imageData.height);
      canvas.getContext('2d').putImageData(layer.imageData, 0, 0);
      compositeContext.drawImage(canvas, layer.left, layer.top);
    }
  }
}
compose(children);
const document = {
  width: N, height: N, channels: 3, colorMode: 3, bitsPerChannel: 8,
  children, imageData: compositeContext.getImageData(0, 0, N, N),
  imageResources: {
    resolutionInfo: { horizontalResolution: 72, horizontalResolutionUnit: 'PPI', widthUnit: 'Inches',
      verticalResolution: 72, verticalResolutionUnit: 'PPI', heightUnit: 'Inches' },
    versionInfo: { hasRealMergedData: true, writerName: '瀚海星云徽标', readerName: 'Adobe Photoshop', fileVersion: 1 },
  },
};
fs.writeFileSync(path.join(OUT, '瀚海星云_预览.png'), composite.toBuffer('image/png'));
fs.writeFileSync(path.join(OUT, '瀚海星云_源文件.psd'), writePsdBuffer(document, { generateThumbnail: true }));
fs.writeFileSync(path.join(WORK, 'layout.json'), JSON.stringify({
  size: N, center, blue, scale, radii, diskRadius, glyphMetrics, centralSize, centralTransform,
  fonts: fontNames, sourceCenter, offset,
}, null, 2));
console.log(JSON.stringify({ output: OUT, size: N, blue, radii, diskRadius,
  text: '中国科大 瀚海星云', centralText: '研', textLayerCount: 9, shapeLayerCount: 6 }, null, 2));
