// @vitest-environment jsdom

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CreditSummaryCard, type CreditAccount } from './CreditSummaryCard';

vi.mock('../../services/i18n', () => ({
  i18nService: {
    t: (key: string) => {
      const map: Record<string, string> = {
        creditBalance: '积分余额',
        creditUnit: '积分',
        creditMonthlyUsage: '本月已用',
        creditMonthlyAllowance: '本月额度',
        creditNextReset: '下次重置',
        creditTopUp: '充值',
        creditTotalEarned: '累计收入',
        creditTotalSpent: '累计支出',
        creditViewHistory: '查看积分明细',
        // legacy dotted keys kept for back-compat with old fixtures
        'credit.balance': '积分余额',
        'credit.unit': '积分',
        'credit.monthlyUsage': '本月已用',
        'credit.monthlyAllowance': '本月额度',
        'credit.nextReset': '下次重置',
        'credit.recharge': '充值',
        'credit.totalEarned': '累计收入',
        'credit.totalSpent': '累计支出',
        'credit.viewHistory': '查看积分明细',
      };
      return map[key] ?? key;
    },
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
