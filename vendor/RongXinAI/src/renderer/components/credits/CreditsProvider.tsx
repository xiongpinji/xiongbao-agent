import React, { createContext, useContext, useState, useCallback } from 'react';
import type { CreditAccount, CreditTransaction } from './CreditSummaryCard';
import { RechargeDialog } from './RechargeDialog';
import type { RechargePlan } from './RechargeDialog';
import { CreditSummaryCard } from './CreditSummaryCard';
import { CreditHistory } from './CreditHistory';

export interface CreditsProviderProps {
  initialAccount?: CreditAccount;
  initialTransactions?: CreditTransaction[];
  rechargePlans?: RechargePlan[];
  onPurchase?: (planId: string) => Promise<void>;
  children: React.ReactNode;
}

interface CreditsContextValue {
  account: CreditAccount;
  transactions: CreditTransaction[];
  openRecharge: () => void;
  openHistory: () => void;
}

const CreditsContext = createContext<CreditsContextValue | null>(null);

const DEFAULT_ACCOUNT: CreditAccount = {
  balance: 0,
  totalEarned: 0,
  totalSpent: 0,
  tier: 'free',
  tierName: '免费版',
};

const DEFAULT_PLANS: RechargePlan[] = [
  { id: 'plan-100', credits: 100, priceCents: 1000, currency: 'CNY' },
  { id: 'plan-500', credits: 500, bonus: 50, priceCents: 4900, currency: 'CNY', popular: true },
  { id: 'plan-1000', credits: 1000, bonus: 150, priceCents: 9500, currency: 'CNY' },
  { id: 'plan-5000', credits: 5000, bonus: 1000, priceCents: 45000, currency: 'CNY' },
];

export function CreditsProvider({
  initialAccount = DEFAULT_ACCOUNT,
  initialTransactions = [],
  rechargePlans = DEFAULT_PLANS,
  onPurchase,
  children,
}: CreditsProviderProps) {
  const [account, setAccount] = useState<CreditAccount>(initialAccount);
  const [transactions, setTransactions] = useState<CreditTransaction[]>(initialTransactions);
  const [rechargeOpen, setRechargeOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const openRecharge = useCallback(() => setRechargeOpen(true), []);
  const openHistory = useCallback(() => setHistoryOpen(true), []);

  const handlePurchase = useCallback(async (planId: string) => {
    if (onPurchase) {
      await onPurchase(planId);
      return;
    }
    setLoading(true);
    const plan = rechargePlans.find((p) => p.id === planId);
    if (!plan) return;
    setAccount((prev) => ({
      ...prev,
      balance: prev.balance + plan.credits + (plan.bonus ?? 0),
      totalEarned: prev.totalEarned + plan.credits + (plan.bonus ?? 0),
    }));
    setTransactions((prev) => [
      {
        id: `tx-${Date.now()}`,
        type: 'recharge',
        amount: plan.credits + (plan.bonus ?? 0),
        description: `充值套餐 ${plan.credits} 积分`,
        timestamp: Date.now(),
        category: 'recharge',
      },
      ...prev,
    ]);
    setLoading(false);
  }, [onPurchase, rechargePlans]);

  return (
    <CreditsContext.Provider value={{ account, transactions, openRecharge, openHistory }}>
      {children}

      <RechargeDialog
        open={rechargeOpen}
        onOpenChange={setRechargeOpen}
        plans={rechargePlans}
        currentBalance={account.balance}
        onPurchase={handlePurchase}
        loading={loading}
      />

      {historyOpen && (
        <CreditHistory
          transactions={transactions}
          loading={false}
          onClose={() => setHistoryOpen(false)}
        />
      )}
    </CreditsContext.Provider>
  );
}

export function useCredits() {
  const ctx = useContext(CreditsContext);
  if (!ctx) {
    throw new Error('useCredits must be used within CreditsProvider');
  }
  return ctx;
}

export { CreditSummaryCard, CreditHistory, RechargeDialog };
