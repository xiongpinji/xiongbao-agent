# 熊宝 Agent 品牌资产说明

## 📁 目录结构

```
octop/contrib/workbuddy/console/assets/brand/
  ├─ logo-icon-28.png       ✅ 28×28侧边栏Logo（2.4 KB）
  ├─ mascot.png             ✅ 140×140吉祥物主图（40 KB）
  ├─ mascot-small.png       ✅ 72×72吉祥物小图（12 KB）
  ├─ logo-icon.jpg          📁 原始LOGO源文件（194 KB）
  ├─ mascot-source.jpg      📁 5种姿态素材源文件（307 KB）
  ├─ yxx-*.svg              🗑️ 旧版文件（勇小熊品牌，已弃用）
  └─ README.md              本文件
```

**品牌资产状态：** ✅ 核心文件已完成（2026-09-18）

---

## ✅ 已完成文件

### 1. `logo-icon-28.png`（必需）
- **用途：** 侧边栏品牌标识
- **尺寸：** 28×28 px
- **格式：** PNG RGB
- **内容：** 金色盾牌小熊LOGO
- **文件大小：** 2.4 KB
- **引用位置：**
  ```html
  <img src="/console/assets/brand/logo-icon-28.png" alt="熊宝" width="28" height="28" />
  ```

### 2. `mascot.png`（主吉祥物）
- **用途：** 登录页、Banner等大尺寸场景
- **尺寸：** 140×140 px
- **格式：** PNG RGB
- **内容：** 正面熊宝吉祥物（川剧变脸风格）
- **文件大小：** 40 KB
- **引用位置：**
  ```html
  <!-- 登录页 -->
  <img class="mascot" src="/console/assets/brand/mascot.png" alt="熊宝" />
  
  <!-- 右侧Banner -->
  <img src="/console/assets/brand/mascot.png" alt="" />
  ```

### 3. `mascot-small.png`（小吉祥物）
- **用途：** 空状态占位、小尺寸场景
- **尺寸：** 72×72 px
- **格式：** PNG RGB
- **内容：** 与mascot.png同源，Lanczos高质量缩放
- **文件大小：** 12 KB
- **引用位置：**
  ```html
  <!-- 空状态 -->
  <img class="empty-mascot" src="/console/assets/brand/mascot-small.png" alt="" width="72" height="72" />
  ```

---

## 🗑️ 旧版文件（已弃用）

以下文件为"勇小熊"品牌资产，已**不再使用**：

```
yxx-logo-icon.svg     → 已替换为 logo-icon-28.png
yxx-mascot.svg        → 已替换为 mascot.png + mascot-small.png
yxx-logo-full.svg     → 暂未使用
yxx-favicon.svg       → 暂未使用
```

**处理建议：** 可保留作为历史备份，或在确认新素材稳定后删除。

---

## 📐 设计规范

### 色彩要求
- **主色调：** 金色 #FFC107（品牌强调）
- **辅色：** 深色背景系（#0F1115 ~ #3A3B40）
- **Logo色彩：** 
  - 熊宝头像：川剧变脸配色（金/红/蓝）
  - 背景：白色或透明

### 风格要求
- **国潮元素：** 保留川剧变脸特征
- **现代简约：** 不过度装饰，适合深色UI
- **友好专业：** 既有亲和力，又不失可信度

### 尺寸标准
| 文件 | 标准尺寸 | 用途 |
|------|---------|------|
| logo-icon-28.png | 28×28 | 侧边栏、导航栏 |
| mascot.png | 140×140 | 登录页、大尺寸Banner |
| mascot-small.png | 72×72 | 空状态、小图标 |

---

## 🔧 技术细节

### 图片处理流程
1. **源文件：** `logo-icon.jpg` (金色盾牌LOGO) + `mascot-source.jpg` (5种姿态横排)
2. **裁切：** mascot-source.jpg 宽度÷5，取第3段（中间姿态）
3. **缩放：** 使用 Lanczos 算法高质量重采样
4. **格式：** PNG RGB（无需透明通道）

### HTML引用规范
```html
<!-- 侧边栏Logo -->
<img src="/console/assets/brand/logo-icon-28.png" 
     alt="熊宝" 
     width="28" 
     height="28" />

<!-- 登录页吉祥物（140×140） -->
<img class="mascot" 
     src="/console/assets/brand/mascot.png" 
     alt="熊宝" />

<!-- 空状态小吉祥物（72×72） -->
<img class="empty-mascot" 
     src="/console/assets/brand/mascot-small.png" 
     alt="" 
     width="72" 
     height="72" />
```

---

## ✅ 验收标准

品牌资产文件需满足：

1. **格式正确：** PNG格式，非JPG/SVG
2. **尺寸精确：** 
   - logo-icon-28.png: 28×28 px
   - mascot.png: 140×140 px
   - mascot-small.png: 72×72 px
3. **视觉清晰：** 深色背景下清晰可辨，无锯齿
4. **文件大小：** 单个文件 < 50KB（已达标）
5. **命名规范：** 全小写，连字符分隔

**当前状态：** ✅ 全部达标

---

## 📝 更新日志

- **2026-09-18** - ✅ 完成核心PNG资产生成（logo-icon-28.png, mascot.png, mascot-small.png）
- **2026-09-18** - 📝 创建品牌资产说明文档
- **2026-09-18** - 🎨 确立"熊宝 Agent"品牌规范

---

**文档版本：** v1.1  
**最后更新：** 2026-09-18 23:05  
**维护者：** 熊宝 Agent 团队
