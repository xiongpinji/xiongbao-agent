#!/usr/bin/env node
/**
 * 调整熊宝品牌资产图片尺寸
 * 将 JPG 转换为 PNG 透明底
 */

const sharp = require('sharp');
const path = require('path');
const fs = require('fs');

const BRAND_DIR = path.join(__dirname, '../src/renderer/assets/brand/xiongbao');

async function resizeImages() {
  console.log('📐 开始调整品牌资产图片尺寸...\n');

  // 1. Logo 图标: 28x28
  const logoSrc = path.join(BRAND_DIR, 'logo-icon-original.jpg');
  const logoDest = path.join(BRAND_DIR, 'logo-icon.png');
  
  if (fs.existsSync(logoSrc)) {
    await sharp(logoSrc)
      .resize(28, 28, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
      .png()
      .toFile(logoDest);
    console.log('✅ Logo 图标已调整为 28×28 px (PNG 透明底)');
  } else {
    console.warn('⚠️  找不到 logo-icon-original.jpg');
  }

  // 2. 吉祥物: 140x140
  const mascotSrc = path.join(BRAND_DIR, 'mascot-original.jpg');
  const mascotDest = path.join(BRAND_DIR, 'mascot.png');
  
  if (fs.existsSync(mascotSrc)) {
    await sharp(mascotSrc)
      .resize(140, 140, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
      .png()
      .toFile(mascotDest);
    console.log('✅ 吉祥物已调整为 140×140 px (PNG 透明底)');
  } else {
    console.warn('⚠️  找不到 mascot-original.jpg');
  }

  console.log('\n🎉 品牌资产调整完成！');
}

resizeImages().catch(err => {
  console.error('❌ 调整失败:', err);
  process.exit(1);
});
