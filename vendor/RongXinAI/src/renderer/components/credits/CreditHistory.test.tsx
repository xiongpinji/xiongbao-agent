// @vitest-environment jsdom

import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { CreditHistory } from './CreditHistory';
import type { CreditTransaction } from './CreditSummaryCard';

const mockTransactions: CreditTransaction[] = [
  { id: '1', type: 'spend', amount: -120, description: 'GPT-4 ????', timestamp: 1000, category: 'chat' },
  { id: '2', type: 'spend', amount: -45, description: 'Claude Sonnet ????', timestamp: 2000, category: 'chat' },
  { id: '3', type: 'recharge', amount: 500, description: '???? 500 ??', timestamp: 3000, category: 'recharge' },
  { id: '4', type: 'earn', amount: 100, description: '??????', timestamp: 4000, category: 'daily' },
  { id: '5', type: 'gift', amount: 200, description: '??????', timestamp: 5000, category: 'invite' },
  { id: '6', type: 'refund', amount: 50, description: '????', timestamp: 6000, category: 'refund' },
];

vi.mock('../../services/i18n', () => ({
  i18nService: {
    t: (key: string) => {
      const map: Record<string, string> = {
        creditHistorySearch: '??',
        creditHistoryFilterAll: '??',
        creditHistoryTypeEarn: '??',
        creditHistoryTypeSpend: '??',
        creditHistoryTypeRecharge: '??',
        creditHistoryTypeGift: '??',
        creditHistoryTypeRefund: '??',
        creditHistoryExport: '??',
        creditHistoryEmpty: '????',
        commonLoading: '???...',
        // legacy dotted keys kept for back-compat with the old test fixtures
        'credit.history.search': '??',
        'credit.history.filterAll': '??',
        'credit.history.typeEarn': '??',
        'credit.history.typeSpend': '??',
        'credit.history.typeRecharge': '??',
        'credit.history.typeGift': '??',
        'credit.history.typeRefund': '??',
        'credit.history.export': '??',
        'credit.history.empty': '????',
        'common.loading': '???...',
      };
      return map[key] ?? key;
    },
  },
}));

describe('CreditHistory', () => {
  it('renders transaction list', () => {
    const { container } = render(<CreditHistory transactions={mockTransactions} />);
    expect(container.textContent).toContain('GPT-4');
    expect(container.textContent).toContain('??');
    expect(container.textContent).toContain('??');
  });

  it('formats positive/negative amounts correctly', () => {
    const { container } = render(<CreditHistory transactions={mockTransactions} />);
    expect(container.textContent).toMatch(/120|500/);
  });

  it('shows empty state when no transactions', () => {
    const { container } = render(<CreditHistory transactions={[]} />);
    expect(container.textContent).toContain('????');
  });

  it('renders loading state', () => {
    const { container } = render(<CreditHistory transactions={[]} loading />);
    expect(container.textContent).toContain('???');
  });

  it('renders filter options', () => {
    const { container } = render(<CreditHistory transactions={mockTransactions} />);
    expect(container.textContent).toContain('??');
    expect(container.textContent).toContain('??');
    expect(container.textContent).toContain('??');
  });

  it('shows export button when onExport provided', () => {
    const onExport = vi.fn();
    const { container } = render(<CreditHistory transactions={mockTransactions} onExport={onExport} />);
    expect(container.textContent).toContain('??');
  });

  it('hides export button when onExport not provided', () => {
    const { container } = render(<CreditHistory transactions={mockTransactions} />);
    expect(container.querySelector('button[title="??"]')).toBeNull();
  });

  it('handles type filter change', () => {
    const onFilter = vi.fn();
    const { container } = render(
      <CreditHistory transactions={mockTransactions} onFilter={onFilter} />,
    );
    const select = container.querySelector('select');
    expect(select).not.toBeNull();
  });
});
