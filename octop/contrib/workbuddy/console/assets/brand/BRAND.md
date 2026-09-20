/* 勇小熊 Agent · 品牌资产说明
 * Brand Assets — 勇小熊 Agent
 * 更新时间：2026-09-18
 *
 * 本目录包含勇小熊 Agent（YongXiaoXiong Agent）的全部品牌资产。
 * 源素材来自用户提供的两张图：品牌展示图（川剧变脸熊猫 + 5种风格 +
 * 三视图 + 表情包）与设计规范页（色板 + 字体 + 圆角 + 间距刻度）。
 *
 * 全部资源由设计规范约束，对外保持一致的视觉识别。
 */

/* ═══════════════════════════════════════
   1. 资产清单
   ═══════════════════════════════════════

  logo-icon.png     (PNG, 256×256)  圆角方形头像，应用图标 / favicon / 侧栏头像
  logo-icon.svg     (SVG)           矢量版本，可任意缩放
  logo-full.png     (PNG, 640×180)  完整 Logo（含"勇小熊 Agent"字样），导航栏 / 启动屏
  logo-full.svg     (SVG)           矢量版本
  mascot.png        (PNG, 512×512)  吉祥物全身像，空状态 / 登录页 / 浮窗
  mascot.svg        (SVG)           矢量版本
  BRAND.md          (本文)          品牌规范
 */

/* ═══════════════════════════════════════
   2. 品牌色板（与 tokens.css 完全同步）
   ═══════════════════════════════════════

  深色背景层级
  --bg-primary:    #0F1115   最深背景（页面底色）
  --bg-secondary:  #1A1B1F   侧边栏 / 分组容器
  --bg-tertiary:   #242529   卡片 / 输入框
  --bg-elevated:   #2D2E33   hover 态 / 浮起
  --bg-overlay:    #3A3B40   弹窗 / 浮层 / Modal

  品牌强调
  --brand-yellow:  #FFC107   主强调（积分徽章 / 激活态 / CTA）
  --brand-red:     #FF4444   危险 / 重要提醒
  --brand-blue:    #4B7BF5   链接 / 信息

  文本层级
  --text-primary:   #F8FAFC   主要正文
  --text-secondary: #C7C9CC   次要文本
  --text-muted:     #8A8D92   辅助 / 占位文本

  兼容保留（WorkBuddy 旧版变量名映射）
  --accent:         #FFC107 ≡ --brand-yellow
  --bg:             #0F1115 ≡ --bg-primary
  --panel:          #242529 ≡ --bg-tertiary
 */

/* ═══════════════════════════════════════
   3. 字体
   ═══════════════════════════════════════

  中文（勇小熊）："PingFang SC", "Microsoft YaHei", "Hiragino Sans GB",
                  "Source Han Sans CN", system-ui
  西文 / 数字：   -apple-system, "SF Pro", "Inter", system-ui
  等宽（代码）：  "JetBrains Mono", "Fira Code", "SF Mono", Menlo, Consolas

  字号刻度（13px 基准，WorkBuddy 标准）
  --fs-xs:    11px   徽章 / 元数据 / 时间戳
  --fs-sm:    12px   次要文本 / 标签
  --fs-base:  13px   正文 / 列表项
  --fs-md:    14px   主文本
  --fs-lg:    16px   标题 / 强强调
  --fs-xl:    20px   卡片标题
  --fs-2xl:   28px   Hero / 大标题

  行高：1.5（紧凑列表 1.4）
 */

/* ═══════════════════════════════════════
   4. 圆角刻度
   ═══════════════════════════════════════

  --radius-xs:   4px   微元素（小标签 / 状态点）
  --radius-sm:   6px   输入框 / 小按钮 / 列表项
  --radius:      8px   卡片 / 普通按钮
  --radius-md:  10px   较大卡片 / 浮起元素
  --radius-lg:  12px   大卡片 / Modal / 大输入框
  --radius-xl:  16px   Hero 容器 / 巨型卡片
  --radius-full: 999px 胶囊（Tag / Chip / 激活态横线）
 */

/* ═══════════════════════════════════════
   5. 间距刻度（4px 基准）
   ═══════════════════════════════════════

  --space-1:    4px
  --space-2:    8px
  --space-3:   12px
  --space-4:   16px
  --space-5:   24px
  --space-6:   32px
  --space-7:   48px
 */

/* ═══════════════════════════════════════
   6. 阴影
   ═══════════════════════════════════════

  --shadow-sm:     0 2px 8px rgba(0,0,0,0.12)     浮起提示
  --shadow:        0 4px 16px rgba(0,0,0,0.18)   卡片默认
  --shadow-lg:     0 8px 32px rgba(0,0,0,0.26)   Modal / Drawer
  --shadow-gold:   0 4px 18px rgba(255,193,7,0.22) 主 CTA / 激活 Logo
 */

/* ═══════════════════════════════════════
   7. Logo 使用规范
   ═══════════════════════════════════════

  最小尺寸：
    - logo-icon.png   ≥ 24px（侧栏头像）
    - logo-full.png   ≥ 120px 宽（启动屏）

  安全区：
    - logo 周围保留 ≥ 16px（与文字 / 边框间距）

  背景适配：
    - 深色场景：使用 logo 原图（金色描边 / 红黑配色）
    - 浅色场景：禁用！勇小熊 logo 仅适配深色背景
    - 顶栏 / 侧栏：使用 logo-icon（圆角方形）

  禁止：
    - 改变主红 / 主黄 / 主黑配比
    - 添加描边 / 投影（除非与原 logo 一致）
    - 旋转 / 倾斜（保持正向）
    - 与低对比度背景叠加
 */

/* ═══════════════════════════════════════
   8. 文案规范
   ═══════════════════════════════════════

  品牌名（全称）：  勇小熊 Agent
  品牌名（简称）：  勇小熊
  英文：          YongXiaoXiong Agent / YXX Agent
  Hero 标题：      勇小熊 Agent，我帮你
  品牌口号：      勇敢做自己！
  角色定位：      川剧变脸熊猫 — 灵动、有戏、不死板

  替换映射（迁移用）：
    WorkBuddy    → 勇小熊 Agent
    熊宝 Agent   → 勇小熊 Agent
    WorkBuddy    → 勇小熊
    熊宝         → 勇小熊
 */

/* ═══════════════════════════════════════
   9. 设计宪法
   ═══════════════════════════════════════

  本目录所有资产 + octop/contrib/workbuddy/console/tokens.css
  必须保持严格一致。任何颜色 / 圆角 / 字体偏离本规范视为缺陷。
  新增资产请同步更新本文件与 tokens.css。
 */
