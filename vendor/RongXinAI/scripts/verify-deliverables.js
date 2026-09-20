#!/usr/bin/env node
/**
 * 验证脚本 - 检查任务 1+2+3 的所有文件是否创建成功
 * 不需要运行 npm install，可独立运行
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const CHECKS = [
  // ============ 任务 1：Workbuddy 主题 + 品牌资产 ============
  {
    task: 1,
    category: '主题文件',
    files: [
      'src/renderer/theme/themes/workbuddy.ts',
      'src/renderer/theme/themes/workbuddy.test.ts',
      'src/renderer/theme/themes/plugins.ts',
      'src/renderer/theme/themes/types.ts',
      'WORKBUDDY_THEME.md',
    ],
  },
  {
    task: 1,
    category: '品牌资产',
    files: [
      'src/renderer/assets/brand/xiongbao/logo-icon.png',
      'src/renderer/assets/brand/xiongbao/mascot.png',
      'src/renderer/assets/brand/xiongbao/logo-icon-original.jpg',
      'src/renderer/assets/brand/xiongbao/mascot-original.jpg',
    ],
  },
  {
    task: 1,
    category: 'React 组件',
    files: [
      'src/renderer/components/brand/ThemeBrandLogo.tsx',
      'src/renderer/components/brand/ThemeBrandMascot.tsx',
      'src/renderer/components/brand/index.ts',
    ],
  },
  {
    task: 1,
    category: '脚本',
    files: [
      'scripts/resize-brand-assets.js',
    ],
  },
  {
    task: 1,
    category: '文档',
    files: [
      'docs/XIONGBAO_BRANDING.md',
      'docs/XIONGBAO_BRANDING_COMPLETION.md',
      'docs/XIONGBAO_BRANDING_SUMMARY.md',
    ],
  },

  // ============ 任务 2：积分系统 ============
  {
    task: 2,
    category: '积分系统组件',
    files: [
      'src/renderer/components/credits/CreditSummaryCard.tsx',
      'src/renderer/components/credits/CreditHistory.tsx',
      'src/renderer/components/credits/RechargeDialog.tsx',
      'src/renderer/components/credits/CreditsProvider.tsx',
      'src/renderer/components/credits/index.ts',
    ],
  },

  // ============ 任务 2：语音输入 ============
  {
    task: 2,
    category: '语音组件',
    files: [
      'src/renderer/components/voice/VoiceInputButton.tsx',
      'src/renderer/components/voice/VoiceOutput.tsx',
      'src/renderer/components/voice/index.ts',
    ],
  },

  // ============ 任务 2：移动端响应式 ============
  {
    task: 2,
    category: '响应式组件',
    files: [
      'src/renderer/components/responsive/Responsive.tsx',
      'src/renderer/components/responsive/ScrollToTop.tsx',
      'src/renderer/components/responsive/MobileChatLayout.tsx',
      'src/renderer/components/responsive/index.ts',
    ],
  },

  // ============ 任务 2：演示页面 ============
  {
    task: 2,
    category: '演示页面',
    files: [
      'src/renderer/components/EnhancementsDemo.tsx',
    ],
  },

  // ============ 任务 3：测试 ============
  {
    task: 3,
    category: '积分系统测试',
    files: [
      'src/renderer/components/credits/CreditSummaryCard.test.tsx',
      'src/renderer/components/credits/CreditHistory.test.tsx',
      'src/renderer/components/credits/RechargeDialog.test.tsx',
    ],
  },
  {
    task: 3,
    category: '语音测试',
    files: [
      'src/renderer/components/voice/VoiceInputButton.test.tsx',
      'src/renderer/components/voice/VoiceOutput.test.tsx',
    ],
  },
  {
    task: 3,
    category: '响应式测试',
    files: [
      'src/renderer/components/responsive/Responsive.test.tsx',
    ],
  },
];

const RESULTS = {
  pass: 0,
  fail: 0,
  total: 0,
  byTask: { 1: { pass: 0, fail: 0 }, 2: { pass: 0, fail: 0 }, 3: { pass: 0, fail: 0 } },
  failures: [],
};

function checkFile(filePath) {
  const fullPath = path.join(ROOT, filePath);
  try {
    const stat = fs.statSync(fullPath);
    return { exists: true, size: stat.size };
  } catch {
    return { exists: false, size: 0 };
  }
}

function checkContent(filePath, patterns) {
  const fullPath = path.join(ROOT, filePath);
  try {
    const content = fs.readFileSync(fullPath, 'utf8');
    const missing = patterns.filter((p) => !content.includes(p));
    return { hasContent: true, missing };
  } catch {
    return { hasContent: false, missing: patterns };
  }
}

console.log('\n🔍 熊宝 Agent 项目验证脚本\n');
console.log('━'.repeat(70));

CHECKS.forEach((group) => {
  console.log(`\n📦 任务 ${group.task} · ${group.category}\n`);

  group.files.forEach((file) => {
    RESULTS.total++;
    const result = checkFile(file);

    if (result.exists) {
      RESULTS.pass++;
      RESULTS.byTask[group.task].pass++;
      const sizeKB = (result.size / 1024).toFixed(1);
      console.log(`  ✅ ${file}  (${sizeKB} KB)`);
    } else {
      RESULTS.fail++;
      RESULTS.byTask[group.task].fail++;
      RESULTS.failures.push(file);
      console.log(`  ❌ ${file}  (MISSING)`);
    }
  });
});

console.log('\n' + '━'.repeat(70));
console.log('\n📊 总体统计\n');
console.log(`  总文件数：${RESULTS.total}`);
console.log(`  ✅ 通过：${RESULTS.pass}`);
console.log(`  ❌ 失败：${RESULTS.fail}`);

Object.entries(RESULTS.byTask).forEach(([task, stats]) => {
  const total = stats.pass + stats.fail;
  const percent = total > 0 ? ((stats.pass / total) * 100).toFixed(0) : '0';
  console.log(`  任务 ${task}：${stats.pass}/${total} (${percent}%)`);
});

if (RESULTS.fail > 0) {
  console.log('\n❌ 失败文件：');
  RESULTS.failures.forEach((f) => console.log(`  - ${f}`));
}

// 内容验证
console.log('\n' + '━'.repeat(70));
console.log('\n🧪 关键内容验证\n');

const contentChecks = [
  {
    file: 'src/renderer/theme/themes/workbuddy.ts',
    mustContain: ['熊宝', 'workbuddy', '#FFC107', '#8A6508', 'branding'],
    description: 'Workbuddy 主题 - 品牌名+金色+branding',
  },
  {
    file: 'src/renderer/theme/themes/plugins.ts',
    mustContain: ['熊宝', 'Xiongbao'],
    description: '主题注册 - 熊宝品牌名',
  },
  {
    file: 'src/renderer/theme/themes/types.ts',
    mustContain: ['ThemeBranding', 'logo', 'mascot', 'productName'],
    description: 'TypeScript 类型 - branding 接口',
  },
  {
    file: 'src/renderer/components/brand/ThemeBrandLogo.tsx',
    mustContain: ['useTheme', 'branding', 'logo', 'alt'],
    description: 'ThemeBrandLogo - 主题集成+无障碍',
  },
  {
    file: 'src/renderer/components/credits/CreditSummaryCard.tsx',
    mustContain: ['CreditAccount', 'balance', 'tierName', 'monthlyAllowance', 'tabular-nums'],
    description: 'CreditSummaryCard - 完整功能',
  },
  {
    file: 'src/renderer/components/credits/CreditHistory.tsx',
    mustContain: ['CreditTransaction', 'type', 'amount', 'description', 'timestamp'],
    description: 'CreditHistory - 完整字段',
  },
  {
    file: 'src/renderer/components/voice/VoiceInputButton.tsx',
    mustContain: ['SpeechRecognition', 'webkitSpeechRecognition', 'continuous', 'interimResults', 'lang'],
    description: 'VoiceInputButton - Web Speech API',
  },
  {
    file: 'src/renderer/components/voice/VoiceOutput.tsx',
    mustContain: ['speechSynthesis', 'SpeechSynthesisUtterance', 'rate', 'pitch', 'lang'],
    description: 'VoiceOutput - TTS API',
  },
  {
    file: 'src/renderer/components/responsive/Responsive.tsx',
    mustContain: ['safe-area-inset', 'md:hidden', 'min-h-[44px]', 'MobileSheet'],
    description: 'Responsive - 安全区+触控友好',
  },
  {
    file: 'src/renderer/components/responsive/MobileChatLayout.tsx',
    mustContain: ['MobileSheet', 'ThemeBrandLogo', 'Mobile', 'drawerOpen', 'md:hidden'],
    description: 'MobileChatLayout - 抽屉+品牌',
  },
];

contentChecks.forEach((check) => {
  const result = checkContent(check.file, check.mustContain);
  if (result.hasContent && result.missing.length === 0) {
    console.log(`  ✅ ${check.description}`);
  } else if (!result.hasContent) {
    console.log(`  ❌ ${check.description} (文件缺失)`);
  } else {
    console.log(`  ⚠️  ${check.description} (缺少: ${result.missing.join(', ')})`);
  }
});

console.log('\n' + '━'.repeat(70));

if (RESULTS.fail === 0) {
  console.log('\n🎉 验证通过！所有文件均已创建。\n');
  process.exit(0);
} else {
  console.log(`\n⚠️  验证完成，但有 ${RESULTS.fail} 个文件缺失。\n`);
  process.exit(1);
}
