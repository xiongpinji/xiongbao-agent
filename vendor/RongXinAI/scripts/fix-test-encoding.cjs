// Fix corrupted test files by regenerating them with proper UTF-8 Chinese text
const fs = require('fs');

const creditHistory = `// @vitest-environment jsdom

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CreditHistory, type CreditTransaction } from './CreditHistory';

vi.mock('../../services/i18n', () => ({
  i18nService: {
    t: (key: string) => key,
    subscribe: () => () => undefined,
    getLanguage: () => 'zh',
  },
}));

const mockTransactions: CreditTransaction[] = [
  { id: '1', type: 'spend', amount: -120, description: 'GPT-4 对话消耗', timestamp: 1000, category: 'chat' },
  { id: '2', type: 'recharge', amount: 500, description: '充值 500 积分', timestamp: 2000, category: 'recharge' },
  { id: '3', type: 'gift', amount: 200, description: '邀请奖励', timestamp: 3000, category: 'invite' },
];

describe('CreditHistory', () => {
  it('renders all transactions by default', () => {
    render(<CreditHistory transactions={mockTransactions} />);
    expect(screen.getByText('GPT-4 对话消耗')).toBeDefined();
    expect(screen.getByText('充值 500 积分')).toBeDefined();
    expect(screen.getByText('邀请奖励')).toBeDefined();
  });

  it('shows empty state when no transactions', () => {
    render(<CreditHistory transactions={[]} />);
    expect(screen.getByText(/暂无|empty/i)).toBeDefined();
  });

  it('shows loading state', () => {
    render(<CreditHistory transactions={[]} loading />);
    expect(screen.getByText(/加载|loading/i)).toBeDefined();
  });

  it('filters by search keyword', () => {
    render(<CreditHistory transactions={mockTransactions} />);
    const input = screen.getByPlaceholderText(/搜索|search/i);
    fireEvent.change(input, { target: { value: 'GPT' } });
    expect(screen.getByText('GPT-4 对话消耗')).toBeDefined();
    expect(screen.queryByText('充值 500 积分')).toBeNull();
  });

  it('filters by type', () => {
    render(<CreditHistory transactions={mockTransactions} />);
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'recharge' } });
    expect(screen.getByText('充值 500 积分')).toBeDefined();
    expect(screen.queryByText('GPT-4 对话消耗')).toBeNull();
  });

  it('formats positive/negative amounts correctly', () => {
    render(<CreditHistory transactions={mockTransactions} />);
    expect(screen.getByText(/^-?120/)).toBeDefined();
    expect(screen.getByText(/^\\+?500|500$/)).toBeDefined();
  });

  it('calls onExport when export button clicked', () => {
    const onExport = vi.fn();
    render(<CreditHistory transactions={mockTransactions} onExport={onExport} />);
    const btn = screen.getByTitle(/导出|export/i);
    fireEvent.click(btn);
    expect(onExport).toHaveBeenCalledOnce();
  });

  it('calls onFilter when search changes', () => {
    const onFilter = vi.fn();
    render(<CreditHistory transactions={mockTransactions} onFilter={onFilter} />);
    const input = screen.getByPlaceholderText(/搜索|search/i);
    fireEvent.change(input, { target: { value: 'test' } });
    expect(onFilter).toHaveBeenCalledWith(
      expect.objectContaining({ keyword: 'test' }),
    );
  });
});
`;

const creditSummaryCard = `// @vitest-environment jsdom

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CreditSummaryCard, type CreditAccount } from './CreditSummaryCard';

vi.mock('../../services/i18n', () => ({
  i18nService: {
    t: (key: string) => key,
    subscribe: () => () => undefined,
    getLanguage: () => 'zh',
  },
}));

const mockAccount: CreditAccount = {
  balance: 1280,
  totalEarned: 5500,
  totalSpent: 4220,
  tier: 'pro',
  tierName: 'Pro 专业版',
  monthlyAllowance: 3000,
  monthlyUsed: 1280,
};

describe('CreditSummaryCard', () => {
  it('renders balance in normal mode', () => {
    render(<CreditSummaryCard account={mockAccount} />);
    expect(screen.getByText('1,280')).toBeDefined();
    expect(screen.getByText('Pro 专业版')).toBeDefined();
  });

  it('renders compact mode', () => {
    render(<CreditSummaryCard account={mockAccount} compact />);
    expect(screen.getByRole('button')).toBeDefined();
  });

  it('shows recharge button when onRecharge provided', () => {
    const onRecharge = vi.fn();
    render(<CreditSummaryCard account={mockAccount} onRecharge={onRecharge} />);
    const button = screen.getByText(/充值|recharge/i);
    fireEvent.click(button);
    expect(onRecharge).toHaveBeenCalledOnce();
  });

  it('shows monthly usage bar when allowance set', () => {
    render(<CreditSummaryCard account={mockAccount} />);
    const bar = document.querySelector('[style*="width"]');
    expect(bar).toBeDefined();
  });

  it('hides monthly usage when no allowance', () => {
    const noAllowance: CreditAccount = { ...mockAccount, monthlyAllowance: undefined };
    render(<CreditSummaryCard account={noAllowance} />);
    expect(document.querySelector('[style*="width"]')).toBeNull();
  });

  it('clamps progress bar to 100%', () => {
    render(
      <CreditSummaryCard
        account={{ ...mockAccount, monthlyUsed: 9999, monthlyAllowance: 1000 }}
      />,
    );
    const bar = document.querySelector('[style*="width"]');
    const width = bar?.getAttribute('style') ?? '';
    expect(width).toContain('100%');
  });

  it('formats numbers with locale separators', () => {
    render(<CreditSummaryCard account={{ ...mockAccount, balance: 1000000 }} />);
    expect(screen.getByText('1,000,000')).toBeDefined();
  });
});
`;

fs.writeFileSync('src/renderer/components/credits/CreditHistory.test.tsx', creditHistory, 'utf8');
console.log('Written CreditHistory.test.tsx');
fs.writeFileSync('src/renderer/components/credits/CreditSummaryCard.test.tsx', creditSummaryCard, 'utf8');
console.log('Written CreditSummaryCard.test.tsx');
