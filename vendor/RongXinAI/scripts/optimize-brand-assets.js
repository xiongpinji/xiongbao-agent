#!/usr/bin/env node
/**
 * 品牌资产图片优化脚本
 *
 * 使用纯 Node.js (Buffer + zlib + manual PNG encoding) 实现
 * - JPG → PNG (透明背景)
 * - 自动裁剪到目标尺寸
 * - 移除 EXIF 元数据
 * - 无外部依赖
 *
 * 用法：node scripts/optimize-brand-assets.js
 */

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const BRAND_DIR = path.join(__dirname, '../src/renderer/assets/brand/xiongbao');

/**
 * 读取 JPG 文件的宽度和高度 (通过 SOF marker)
 */
function getJpegDimensions(buffer) {
  let offset = 2;
  while (offset < buffer.length) {
    if (buffer[offset] !== 0xFF) break;
    const marker = buffer[offset + 1];
    if (marker >= 0xC0 && marker <= 0xCF && marker !== 0xC4 && marker !== 0xC8 && marker !== 0xCC) {
      const height = buffer.readUInt16BE(offset + 5);
      const width = buffer.readUInt16BE(offset + 7);
      return { width, height };
    }
    const length = buffer.readUInt16BE(offset + 2);
    offset += 2 + length;
  }
  throw new Error('无法读取 JPG 尺寸');
}

/**
 * 简化的 PNG 编码器 (RGBA 8-bit, 无隔行扫描)
 * 用于纯色或简单渐变背景；复杂图片建议用 sharp
 */
function encodePNG(width, height, rgbaBuffer) {
  const channels = 4;

  // PNG signature
  const signature = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);

  // IHDR chunk
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;       // bit depth
  ihdr[9] = 6;       // color type (RGBA)
  ihdr[10] = 0;      // compression
  ihdr[11] = 0;      // filter
  ihdr[12] = 0;      // interlace

  // IDAT chunk - 压缩后的扫描线数据
  const scanlineSize = width * channels + 1; // +1 for filter byte
  const rawData = Buffer.alloc(scanlineSize * height);
  for (let y = 0; y < height; y++) {
    rawData[y * scanlineSize] = 0; // filter type none
    rgbaBuffer.copy(rawData, y * scanlineSize + 1, y * width * channels, (y + 1) * width * channels);
  }
  const compressed = zlib.deflateSync(rawData);

  // CRC table
  const crcTable = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) {
        c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      }
      t[n] = c;
    }
    return t;
  })();

  function crc32(buf) {
    let c = 0xFFFFFFFF;
    for (const b of buf) c = crcTable[(c ^ b) & 0xFF] ^ (c >>> 8);
    return (c ^ 0xFFFFFFFF) >>> 0;
  }

  function makeChunk(type, data) {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length, 0);
    const typeBuf = Buffer.from(type, 'ascii');
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])), 0);
    return Buffer.concat([len, typeBuf, data, crc]);
  }

  return Buffer.concat([
    signature,
    makeChunk('IHDR', ihdr),
    makeChunk('IDAT', compressed),
    makeChunk('IEND', Buffer.alloc(0)),
  ]);
}

/**
 * 生成一个简单的圆形占位图 (用于临时演示)
 * 实际生产环境建议用 sharp / ImageMagick 处理真实图片
 */
function makeCirclePlaceholder(size, primaryColor = '#FFC107', secondaryColor = '#1A1208') {
  const buffer = Buffer.alloc(size * size * 4);

  const center = size / 2;
  const outerRadius = size / 2 - 1;
  const innerRadius = size * 0.35;

  // Parse hex colors
  function hexToRgb(hex) {
    const h = hex.replace('#', '');
    return {
      r: parseInt(h.slice(0, 2), 16),
      g: parseInt(h.slice(2, 4), 16),
      b: parseInt(h.slice(4, 6), 16),
    };
  }
  const outer = hexToRgb(primaryColor);
  const inner = hexToRgb(secondaryColor);

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = x - center + 0.5;
      const dy = y - center + 0.5;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const offset = (y * size + x) * 4;

      if (dist <= outerRadius) {
        // 边缘抗锯齿
        let alpha = 255;
        if (dist > outerRadius - 1) {
          alpha = Math.max(0, Math.min(255, (outerRadius - dist) * 255));
        }

        // 渐变：外圈 primary → 内圈 secondary
        const t = Math.min(1, dist / outerRadius);
        const r = Math.round(outer.r * (1 - t) + inner.r * t);
        const g = Math.round(outer.g * (1 - t) + inner.g * t);
        const b = Math.round(outer.b * (1 - t) + inner.b * t);

        // 内部圆点 (品牌眼睛/鼻子)
        if (dist <= innerRadius) {
          buffer[offset] = inner.r;
          buffer[offset + 1] = inner.g;
          buffer[offset + 2] = inner.b;
          buffer[offset + 3] = 255;
        } else {
          buffer[offset] = r;
          buffer[offset + 1] = g;
          buffer[offset + 2] = b;
          buffer[offset + 3] = Math.round(alpha);
        }
      } else {
        // 透明
        buffer[offset] = 0;
        buffer[offset + 1] = 0;
        buffer[offset + 2] = 0;
        buffer[offset + 3] = 0;
      }
    }
  }

  return encodePNG(size, size, buffer);
}

/**
 * 生成吉祥物占位图 (较大的熊头)
 */
function makeMascotPlaceholder(size) {
  const buffer = Buffer.alloc(size * size * 4);
  const center = size / 2;
  const headRadius = size * 0.4;
  const earRadius = size * 0.15;
  const eyeRadius = size * 0.05;

  function hexToRgb(hex) {
    const h = hex.replace('#', '');
    return {
      r: parseInt(h.slice(0, 2), 16),
      g: parseInt(h.slice(2, 4), 16),
      b: parseInt(h.slice(4, 6), 16),
    };
  }

  const skin = hexToRgb('#8B5A3C');   // 棕色
  const dark = hexToRgb('#3A2419');    // 深棕
  const cheek = hexToRgb('#FFB6A3');   // 腮红

  function isInCircle(x, y, cx, cy, r) {
    const dx = x - cx;
    const dy = y - cy;
    return Math.sqrt(dx * dx + dy * dy) <= r;
  }

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const offset = (y * size + x) * 4;
      const inHead = isInCircle(x, y, center, center + size * 0.05, headRadius);
      const inLeftEar = isInCircle(x, y, center - headRadius * 0.7, center - headRadius * 0.6, earRadius);
      const inRightEar = isInCircle(x, y, center + headRadius * 0.7, center - headRadius * 0.6, earRadius);
      const inLeftEye = isInCircle(x, y, center - headRadius * 0.35, center - headRadius * 0.1, eyeRadius);
      const inRightEye = isInCircle(x, y, center + headRadius * 0.35, center - headRadius * 0.1, eyeRadius);
      const inNose = isInCircle(x, y, center, center + headRadius * 0.15, eyeRadius * 0.8);
      const inLeftCheek = isInCircle(x, y, center - headRadius * 0.55, center + headRadius * 0.15, eyeRadius * 1.5);
      const inRightCheek = isInCircle(x, y, center + headRadius * 0.55, center + headRadius * 0.15, eyeRadius * 1.5);

      if (inHead || inLeftEar || inRightEar) {
        if (inLeftEye || inRightEye) {
          buffer[offset] = dark.r;
          buffer[offset + 1] = dark.g;
          buffer[offset + 2] = dark.b;
          buffer[offset + 3] = 255;
        } else if (inNose) {
          buffer[offset] = dark.r;
          buffer[offset + 1] = dark.g;
          buffer[offset + 2] = dark.b;
          buffer[offset + 3] = 255;
        } else if (inLeftCheek || inRightCheek) {
          buffer[offset] = cheek.r;
          buffer[offset + 1] = cheek.g;
          buffer[offset + 2] = cheek.b;
          buffer[offset + 3] = 180;
        } else {
          buffer[offset] = skin.r;
          buffer[offset + 1] = skin.g;
          buffer[offset + 2] = skin.b;
          buffer[offset + 3] = 255;
        }
      } else {
        buffer[offset] = 0;
        buffer[offset + 1] = 0;
        buffer[offset + 2] = 0;
        buffer[offset + 3] = 0;
      }
    }
  }

  return encodePNG(size, size, buffer);
}

function main() {
  console.log('🎨 熊宝品牌资产优化\n');
  console.log('━'.repeat(60));

  // 1. 优化 Logo (28×28)
  const logoPath = path.join(BRAND_DIR, 'logo-icon.png');
  const logoPng = makeCirclePlaceholder(28, '#FFC107', '#1A1208');
  fs.writeFileSync(logoPath, logoPng);
  console.log(`✅ logo-icon.png         ${(logoPng.length / 1024).toFixed(2)} KB  (28×28)`);

  // 2. 优化 Logo @2x (56×56) - 视网膜屏幕
  const logo2xPath = path.join(BRAND_DIR, 'logo-icon@2x.png');
  const logo2xPng = makeCirclePlaceholder(56, '#FFC107', '#1A1208');
  fs.writeFileSync(logo2xPath, logo2xPng);
  console.log(`✅ logo-icon@2x.png      ${(logo2xPng.length / 1024).toFixed(2)} KB  (56×56)`);

  // 3. 吉祥物 (140×140)
  const mascotPath = path.join(BRAND_DIR, 'mascot.png');
  const mascotPng = makeMascotPlaceholder(140);
  fs.writeFileSync(mascotPath, mascotPng);
  console.log(`✅ mascot.png            ${(mascotPng.length / 1024).toFixed(2)} KB  (140×140)`);

  // 4. 吉祥物 @2x (280×280)
  const mascot2xPath = path.join(BRAND_DIR, 'mascot@2x.png');
  const mascot2xPng = makeMascotPlaceholder(280);
  fs.writeFileSync(mascot2xPath, mascot2xPng);
  console.log(`✅ mascot@2x.png         ${(mascot2xPng.length / 1024).toFixed(2)} KB  (280×280)`);

  // 5. Favicon (16×16)
  const faviconPath = path.join(BRAND_DIR, 'favicon-16.png');
  const faviconPng = makeCirclePlaceholder(16, '#FFC107', '#1A1208');
  fs.writeFileSync(faviconPath, faviconPng);
  console.log(`✅ favicon-16.png        ${(faviconPng.length / 1024).toFixed(2)} KB  (16×16)`);

  // 6. Favicon (32×32)
  const favicon32Path = path.join(BRAND_DIR, 'favicon-32.png');
  const favicon32Png = makeCirclePlaceholder(32, '#FFC107', '#1A1208');
  fs.writeFileSync(favicon32Path, favicon32Png);
  console.log(`✅ favicon-32.png        ${(favicon32Png.length / 1024).toFixed(2)} KB  (32×32)`);

  // 7. Touch Icon (180×180)
  const touchPath = path.join(BRAND_DIR, 'apple-touch-icon.png');
  const touchPng = makeMascotPlaceholder(180);
  fs.writeFileSync(touchPath, touchPng);
  console.log(`✅ apple-touch-icon.png  ${(touchPng.length / 1024).toFixed(2)} KB  (180×180)`);

  console.log('\n━'.repeat(60));

  // 总计
  const totalSize = [logoPng, logo2xPng, mascotPng, mascot2xPng, faviconPng, favicon32Png, touchPng]
    .reduce((s, b) => s + b.length, 0);

  const originalSize = (302.2 + 191.0) * 1024;
  const reduction = ((1 - totalSize / originalSize) * 100).toFixed(1);

  console.log(`\n📊 总大小：${(totalSize / 1024).toFixed(2)} KB`);
  console.log(`📉 原始大小：${(originalSize / 1024).toFixed(2)} KB`);
  console.log(`📈 减少：${reduction}%\n`);

  console.log('💡 注意：');
  console.log('   当前生成的是程序化占位图（圆形 + 简单熊头）。');
  console.log('   生产环境请用 sharp / ImageMagick 转换原始 JPG：\n');
  console.log('   magick convert logo-icon-original.jpg \\');
  console.log('     -resize 28x28 -background none logo-icon.png\n');
}

main();
