// @vitest-environment jsdom

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RechargeDialog, type RechargePlan } from './RechargeDialog';

vi.mock('../../services/i18n', () => ({
  i18nService: {
    t: (key: string) => key,
    subscribe: () => () => undefined,
    getLanguage: () => 'zh',
  },
}));

const mockPlans: RechargePlan[] = [
  { id: 'p1', credits: 100, priceCents: 1000, currency: 'CNY' },
  { id: 'p2', credits: 500, bonus: 50, priceCents: 4900, currency: 'CNY', popular: true },
  { id: 'p3', credits: 1000, bonus: 150, priceCents: 9500, currency: 'CNY' },
];

describe('RechargeDialog', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <RechargeDialog open={false} onOpenChange={() => {}} plans={mockPlans} />,
    );
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it('renders all plans when open', () => {
    render(<RechargeDialog open onOpenChange={() => {}} plans={mockPlans} />);
    expect(screen.getByText(/¥10\.00|10\.00/)).toBeDefined();
    expect(screen.getByText(/¥49\.00|49\.00/)).toBeDefined();
    expect(screen.getByText(/¥95\.00|95\.00/)).toBeDefined();
  });

  it('shows popular badge on popular plan', () => {
    render(<RechargeDialog open onOpenChange={() => {}} plans={mockPlans} />);
    expect(screen.getByText(/热门|popular/i)).toBeDefined();
  });

  it('shows bonus credits when available', () => {
    render(<RechargeDialog open onOpenChange={() => {}} plans={mockPlans} />);
    expect(screen.getByText('+50')).toBeDefined();
    expect(screen.getByText('+150')).toBeDefined();
  });

  it('shows current balance when provided', () => {
    render(
      <RechargeDialog
        open
        onOpenChange={() => {}}
        plans={mockPlans}
        currentBalance={1280}
      />,
    );
    expect(screen.getByText(/1,280/)).toBeDefined();
  });

  it('calls onPurchase with selected plan id', async () => {
    const onPurchase = vi.fn().mockResolvedValue(undefined);
    render(
      <RechargeDialog
        open
        onOpenChange={() => {}}
        plans={mockPlans}
        onPurchase={onPurchase}
      />,
    );
    const plan2Button = screen.getByText('500').closest('button')!;
    fireEvent.click(plan2Button);
    const confirmBtn = screen.getByText(/确认|confirm/i);
    fireEvent.click(confirmBtn);
    await waitFor(() => expect(onPurchase).toHaveBeenCalledWith('p2'));
  });

  it('disables confirm button when no plan selected', () => {
    render(<RechargeDialog open onOpenChange={() => {}} plans={mockPlans} />);
    const confirmBtn = screen.getByText(/确认|confirm/i).closest('button')!;
    expect(confirmBtn).toHaveProperty('disabled', true);
  });

  it('closes dialog after successful purchase', async () => {
    const onOpenChange = vi.fn();
    const onPurchase = vi.fn().mockResolvedValue(undefined);
    render(
      <RechargeDialog
        open
        onOpenChange={onOpenChange}
        plans={mockPlans}
        onPurchase={onPurchase}
      />,
    );
    fireEvent.click(screen.getByText('500').closest('button')!);
    fireEvent.click(screen.getByText(/确认|confirm/i));
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });
});
