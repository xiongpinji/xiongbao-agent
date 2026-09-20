import React, { useState } from 'react';
import { Coins, Mic, Sparkles, Smartphone, ArrowRight, Search, Bell } from 'lucide-react';
import {
  CreditSummaryCard,
  CreditHistory,
  RechargeDialog,
  type CreditAccount,
  type CreditTransaction,
  type RechargePlan,
} from './credits';
import { VoiceInputButton, VoiceOutput } from './voice';
import {
  MobileChatLayout,
  MobileBottomNav,
  ResponsiveContainer,
  ResponsiveGrid,
  ScrollToTop,
  Show,
  Hide,
  MobileOnly,
  DesktopOnly,
} from './responsive';

const MOCK_ACCOUNT: CreditAccount = {
  balance: 1280,
  totalEarned: 5500,
  totalSpent: 4220,
  tier: 'pro',
  tierName: 'Pro 专业版',
  monthlyAllowance: 3000,
  monthlyUsed: 1280,
  nextResetAt: Date.now() + 1000 * 60 * 60 * 24 * 12,
};

const MOCK_TRANSACTIONS: CreditTransaction[] = [
  { id: '1', type: 'spend', amount: -120, description: 'GPT-4 对话消耗', timestamp: Date.now() - 3600_000, category: 'chat' },
  { id: '2', type: 'spend', amount: -45, description: 'Claude Sonnet 对话消耗', timestamp: Date.now() - 7200_000, category: 'chat' },
  { id: '3', type: 'recharge', amount: 500, description: '充值套餐 500 积分', timestamp: Date.now() - 86400_000, category: 'recharge' },
  { id: '4', type: 'earn', amount: 100, description: '每日签到奖励', timestamp: Date.now() - 172800_000, category: 'daily' },
  { id: '5', type: 'gift', amount: 200, description: '邀请好友奖励', timestamp: Date.now() - 259200_000, category: 'invite' },
  { id: '6', type: 'spend', amount: -80, description: '图像生成消耗', timestamp: Date.now() - 345600_000, category: 'image' },
];

const MOCK_PLANS: RechargePlan[] = [
  { id: 'p100', credits: 100, priceCents: 1000, currency: 'CNY' },
  { id: 'p500', credits: 500, bonus: 50, priceCents: 4900, currency: 'CNY', popular: true },
  { id: 'p1000', credits: 1000, bonus: 150, priceCents: 9500, currency: 'CNY' },
  { id: 'p5000', credits: 5000, bonus: 1000, priceCents: 45000, currency: 'CNY' },
];

const SAMPLE_RESPONSES = [
  '我帮你查了一下，今天北京晴转多云，气温 22°C，空气质量良好。',
  '好的，我已经将日程添加到日历，2026 年 9 月 19 日上午 10 点提醒。',
  '共找到 12 条相关文档，最相关的是「工作流自动化最佳实践」。',
];

export function EnhancementsDemo() {
  const [rechargeOpen, setRechargeOpen] = useState(false);
  const [voiceTranscript] = useState('');
  const [text, setText] = useState('');
  const [responseIndex, setResponseIndex] = useState(0);

  const handleVoiceFinal = (final: string) => {
    setText((prev) => (prev ? `${prev} ${final}` : final).trim());
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Hero 标题 */}
      <section className="border-b border-border bg-gradient-to-br from-(--zy-primary-muted) to-background px-4 py-8 sm:px-8 sm:py-12">
        <div className="mx-auto max-w-5xl">
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-(--zy-primary)/30 bg-(--zy-primary-muted) px-3 py-1 text-xs font-medium text-(--zy-primary)">
            <Sparkles className="size-3.5" />
            任务 2 · 功能增强演示
          </div>
          <h1 className="text-2xl font-semibold sm:text-3xl">
            积分系统 · 语音输入 · 移动端适配
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground sm:text-base">
            三大功能模块的完整演示。所有组件都遵循主题系统（workbuddy / codex）并支持明暗模式。
          </p>
        </div>
      </section>

      <ResponsiveContainer className="space-y-10">
        {/* ================== 1. 积分系统 ================== */}
        <section>
          <SectionHeader
            icon={<Coins className="size-5 text-(--zy-primary)" />}
            title="积分系统"
            description="余额展示、月度用量、交易历史、充值套餐"
          />
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="lg:col-span-1">
              <CreditSummaryCard
                account={MOCK_ACCOUNT}
                onRecharge={() => setRechargeOpen(true)}
                onViewHistory={() => {
                  document.getElementById('credit-history')?.scrollIntoView({ behavior: 'smooth' });
                }}
              />
              <div className="mt-3">
                <h4 className="mb-2 text-xs font-medium text-muted-foreground">紧凑模式（侧边栏使用）</h4>
                <CreditSummaryCard
                  account={MOCK_ACCOUNT}
                  compact
                  onViewHistory={() => undefined}
                />
              </div>
            </div>
            <div id="credit-history" className="lg:col-span-2">
              <h3 className="mb-2 text-sm font-medium">交易历史</h3>
              <div className="overflow-hidden rounded-xl border border-border bg-surface">
                <CreditHistory
                  transactions={MOCK_TRANSACTIONS}
                  onExport={() => alert('导出 CSV...')}
                />
              </div>
            </div>
          </div>

          <RechargeDialog
            open={rechargeOpen}
            onOpenChange={setRechargeOpen}
            plans={MOCK_PLANS}
            currentBalance={MOCK_ACCOUNT.balance}
            onPurchase={async (planId: string) => {
              await new Promise((r) => setTimeout(r, 800));
              alert(`购买套餐 ${planId} 成功！`);
            }}
          />
        </section>

        {/* ================== 2. 语音输入 ================== */}
        <section>
          <SectionHeader
            icon={<Mic className="size-5 text-(--zy-destructive)" />}
            title="语音输入 / 输出"
            description="Web Speech API 集成，支持中文、连续模式、静音自动停止"
          />
          <ResponsiveGrid cols={{ mobile: 1, tablet: 2, desktop: 2 }} gap="md">
            <DemoCard title="语音输入（点击麦克风）">
              <div className="flex items-start gap-3">
                <VoiceInputButton
                  size="lg"
                  lang="zh-CN"
                  continuous
                  onFinalTranscript={handleVoiceFinal}
                />
                <div className="flex-1">
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="点击麦克风开始语音输入，或在此输入..."
                    className="min-h-[120px] w-full resize-none rounded-lg border border-border bg-background p-3 text-sm outline-none focus:border-(--zy-primary) focus:ring-2 focus:ring-(--zy-primary-muted)"
                  />
                </div>
              </div>
              {voiceTranscript && (
                <div className="mt-2 rounded-lg bg-(--zy-primary-muted) px-3 py-2 text-xs text-(--zy-primary)">
                  实时转写：{voiceTranscript}
                </div>
              )}
              <p className="mt-2 text-xs text-muted-foreground">
                需要麦克风权限。第一次点击时会弹出授权对话框。
              </p>
            </DemoCard>

            <DemoCard title="语音输出（TTS 朗读）">
              <div className="space-y-3">
                {SAMPLE_RESPONSES.map((resp, i) => (
                  <div
                    key={i}
                    className={`group rounded-lg border p-3 text-sm transition-colors ${
                      responseIndex === i ? 'border-(--zy-primary) bg-(--zy-primary-muted)' : 'border-border bg-background'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="flex-1">{resp}</p>
                      <div className="flex shrink-0 items-center gap-1">
                        <button
                          type="button"
                          onClick={() => setResponseIndex(i)}
                          className="text-xs text-muted-foreground hover:text-(--zy-primary)"
                        >
                          选择
                        </button>
                        <VoiceOutput text={resp} lang="zh-CN" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-3 rounded-lg bg-(--zy-surface-raised) p-3 text-xs text-muted-foreground">
                <p>选中后：</p>
                <p className="mt-1">朗读：{SAMPLE_RESPONSES[responseIndex]}</p>
              </div>
            </DemoCard>
          </ResponsiveGrid>
        </section>

        {/* ================== 3. 移动端适配 ================== */}
        <section>
          <SectionHeader
            icon={<Smartphone className="size-5 text-(--zy-tier-basic-foreground)" />}
            title="移动端响应式"
            description="移动端 AppBar、底部导航、抽屉式面板、安全区适配"
          />

          <div className="grid gap-6 lg:grid-cols-3">
            <DemoCard title="移动端聊天布局">
              <div className="overflow-hidden rounded-lg border border-border">
                <MobileChatLayout
                  drawerContent={
                    <div className="p-4">
                      <h4 className="mb-2 text-sm font-semibold">会话列表</h4>
                      <div className="space-y-1">
                        {['工作汇报', '产品讨论', '学习计划', '代码审查'].map((s) => (
                          <button
                            key={s}
                            type="button"
                            className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-(--zy-surface-raised)"
                          >
                            <span>{s}</span>
                            <ArrowRight className="size-3.5 text-muted-foreground" />
                          </button>
                        ))}
                      </div>
                    </div>
                  }
                  settingsContent={
                    <div className="p-4 text-sm">
                      <p>主题、字体、通知设置等。</p>
                    </div>
                  }
                  title="工作汇报"
                >
                  <div className="h-64 overflow-y-auto bg-background p-4 md:h-96">
                    <div className="space-y-3">
                      {['用户', 'AI 助手', '用户', 'AI 助手'].map((role, i) => (
                        <div
                          key={i}
                          className={`flex ${role === '用户' ? 'justify-end' : 'justify-start'}`}
                        >
                          <div
                            className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                              role === '用户'
                                ? 'bg-(--zy-primary) text-(--zy-primary-foreground)'
                                : 'bg-(--zy-surface-raised) text-foreground'
                            }`}
                          >
                            {role === '用户' ? '请帮我整理本周的工作内容。' : '好的，我来帮你生成一份工作周报...'}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </MobileChatLayout>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                ↑ 拖拽浏览器窗口至 <span className="font-mono">&lt;768px</span> 查看移动端布局
              </p>
            </DemoCard>

            <DemoCard title="底部 Tab Bar">
              <div className="relative overflow-hidden rounded-lg border border-border bg-background" style={{ height: 240 }}>
                <div className="h-full overflow-y-auto p-4 text-sm">
                  <p className="text-muted-foreground">滚动查看底部导航...</p>
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="mt-3 h-12 rounded-lg bg-(--zy-surface-raised)" />
                  ))}
                </div>
                <MobileBottomNav
                  items={[
                    { id: 'chat', label: '对话', icon: <Sparkles className="size-5" />, onClick: () => {}, active: true },
                    { id: 'tasks', label: '任务', icon: <Bell className="size-5" />, onClick: () => {}, badge: 3 },
                    { id: 'credits', label: '积分', icon: <Coins className="size-5" />, onClick: () => {} },
                    { id: 'settings', label: '设置', icon: <Smartphone className="size-5" />, onClick: () => {} },
                  ]}
                />
              </div>
            </DemoCard>

            <DemoCard title="断点工具">
              <div className="space-y-2 text-xs">
                <Show minWidth="md">
                  <div className="rounded-lg border border-(--zy-primary)/40 bg-(--zy-primary-muted) px-3 py-2 text-(--zy-primary)">
                    显示（≥768px）
                  </div>
                </Show>
                <Hide minWidth="md">
                  <div className="rounded-lg border border-(--zy-warning)/40 bg-(--zy-surface-raised) px-3 py-2 text-(--zy-warning)">
                    显示（&lt;768px）
                  </div>
                </Hide>
                <MobileOnly>
                  <div className="rounded-lg border border-(--zy-success)/40 bg-(--zy-surface-raised) px-3 py-2 text-(--zy-success)">
                    MobileOnly
                  </div>
                </MobileOnly>
                <DesktopOnly>
                  <div className="rounded-lg border border-(--zy-tier-enterprise-foreground)/40 bg-(--zy-surface-raised) px-3 py-2 text-(--zy-tier-enterprise-foreground)">
                    DesktopOnly
                  </div>
                </DesktopOnly>
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                缩小浏览器窗口查看效果。
              </p>
            </DemoCard>
          </div>
        </section>

        {/* ================== 文件清单 ================== */}
        <section>
          <SectionHeader
            icon={<Search className="size-5 text-(--zy-success)" />}
            title="交付物清单"
            description="本次任务新增的所有文件"
          />
          <div className="grid gap-4 md:grid-cols-3">
            <FileGroup
              title="积分系统 (credits/)"
              files={[
                'CreditSummaryCard.tsx · 余额卡片',
                'CreditHistory.tsx · 交易历史',
                'RechargeDialog.tsx · 充值弹窗',
                'CreditsProvider.tsx · 上下文 Provider',
                'index.ts · 统一导出',
              ]}
            />
            <FileGroup
              title="语音输入 (voice/)"
              files={[
                'VoiceInputButton.tsx · 麦克风按钮',
                'VoiceOutput.tsx · TTS 朗读控件',
                'index.ts · 统一导出',
              ]}
            />
            <FileGroup
              title="移动端响应式 (responsive/)"
              files={[
                'Responsive.tsx · Show/Hide/MobileOnly 等',
                'ScrollToTop.tsx · 回到顶部',
                'MobileChatLayout.tsx · AppBar + 抽屉',
                'index.ts · 统一导出',
              ]}
            />
          </div>
        </section>
      </ResponsiveContainer>

      <ScrollToTop />
    </div>
  );
}

function SectionHeader({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="mb-4 flex items-start gap-3">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-(--zy-surface-raised)">
        {icon}
      </div>
      <div className="min-w-0">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

function DemoCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-medium">{title}</h3>
      {children}
    </div>
  );
}

function FileGroup({ title, files }: { title: string; files: string[] }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h4 className="mb-2 text-sm font-semibold">{title}</h4>
      <ul className="space-y-1 text-xs text-muted-foreground">
        {files.map((f) => (
          <li key={f} className="font-mono">
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default EnhancementsDemo;
