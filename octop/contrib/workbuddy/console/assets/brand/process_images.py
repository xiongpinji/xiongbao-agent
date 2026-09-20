# -*- coding: utf-8 -*-
"""熊宝 Agent 品牌资产处理脚本"""
from PIL import Image
import os

brand_dir = r'D:\AI编程库\项目库\进行中的项目\xiongbao agent\octop\contrib\workbuddy\console\assets\brand'

# 1. 处理 LOGO（金色盾牌小熊）
logo_src = os.path.join(brand_dir, 'logo-icon.jpg')
logo_img = Image.open(logo_src)
print(f'原始LOGO尺寸: {logo_img.size}')

# 缩放到 28x28（侧边栏用）
logo_28 = logo_img.resize((28, 28), Image.Resampling.LANCZOS)
logo_28.save(os.path.join(brand_dir, 'logo-icon-28.png'))
print('✅ logo-icon-28.png (28x28)')

# 2. 处理吉祥物素材（5种姿态）
mascot_src = os.path.join(brand_dir, 'mascot-source.jpg')
mascot_img = Image.open(mascot_src)
print(f'\n原始素材尺寸: {mascot_img.size}')

# 从5种姿态中选择中间的一个（正面或3/4侧面）
# 假设素材是横向排列，我选择中间位置的熊
width, height = mascot_img.size
single_width = width // 5  # 每个姿态的宽度

# 选择第3个（中间）
center_bear = mascot_img.crop((single_width * 2, 0, single_width * 3, height))
print(f'裁切第3个姿态: {center_bear.size}')

# 转为方形（取最小边）
min_side = min(center_bear.size)
left = (center_bear.width - min_side) // 2
top = (center_bear.height - min_side) // 2
square_bear = center_bear.crop((left, top, left + min_side, top + min_side))

# 生成多个尺寸
mascot_140 = square_bear.resize((140, 140), Image.Resampling.LANCZOS)
mascot_140.save(os.path.join(brand_dir, 'mascot.png'))
print('✅ mascot.png (140x140)')

mascot_72 = square_bear.resize((72, 72), Image.Resampling.LANCZOS)
mascot_72.save(os.path.join(brand_dir, 'mascot-small.png'))
print('✅ mascot-small.png (72x72)')

print('\n✅ 所有品牌资产处理完成！')
