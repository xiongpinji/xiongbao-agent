import { useMemo } from 'react';
import { i18nService } from '../../services/i18n';
import { Coins, TrendingUp, TrendingDown, Sparkles, ChevronRight } from 'lucide-react';
import { cn } from '@shared/lib/utils';

export interface CreditTransaction {
  id: string;
  type: 'spend' | 'earn' | 'recharge' | 'gift' | 'refund';
  amount: number;
  description: string;
  timestamp: number;
  category?: string;
}

export interface CreditAccount {
  balance: number;
  totalEarned: number;
  totalSpent: number;
  tier: 'free' | 'basic' | 'pro' | 'enterprise';
  tierName: string;
  nextResetAt?: number;
  monthlyAllowance?: number;
  monthlyUsed?: number;
}

export interface CreditSummaryCardProps {
  account: CreditAccount;
  onRecharge?: () => void;
  onViewHistory?: () => void;
  compact?: boolean;
  className?: string;
}

export function CreditSummaryCard({
  account,
  onRecharge,
  onViewHistory,
  compact = false,
  className,
}: CreditSummaryCardProps) {
  const { t } = { t: (key: string, fallback?: string) => i18nService.t(key) ?? fallback ?? key };
  const tierColors = useMemo(() => {
    switch (account.tier) {
      case 'free':
        return 'bg-(--zy-tier-free-background) text-(--zy-tier-free-foreground)';
      case 'basic':
        return 'bg-(--zy-tier-basic-background) text-(--zy-tier-basic-foreground)';
      case 'pro':
        return 'bg-(--zy-tier-pro-background) text-(--zy-tier-pro-foreground)';
      case 'enterprise':
        return 'bg-(--zy-tier-enterprise-background) text-(--zy-tier-enterprise-foreground)';
    }
  }, [account.tier]);

  const monthlyPercent = useMemo(() => {
    if (!account.monthlyAllowance) return 0;
    return Math.min(100, (account.monthlyUsed ?? 0) / account.monthlyAllowance * 100);
  }, [account.monthlyAllowance, account.monthlyUsed]);

  if (compact) {
    return (
      <button
        type="button"
        onClick={onViewHistory}
        className={cn(
          'group flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm transition-all hover:border-(--zy-primary) hover:bg-(--zy-primary-muted)',
          className,
        )}
      >
        <Coins className="size-4 text-(--zy-primary)" />
        <span className="font-semibold tabular-nums">{account.balance.toLocaleString()}</span>
        <ChevronRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
      </button>
    );
  }

  return (
    <div className={cn(
      'rounded-xl border border-border bg-surface p-4 shadow-sm',
      className,
    )}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-full bg-(--zy-primary-muted)">
            <Coins className="size-5 text-(--zy-primary)" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">{t('creditBalance')}</span>
              <span className={cn('rounded-full px-1.5 py-0.5 text-[10px] font-medium', tierColors)}>
                {account.tierName}
              </span>
            </div>
            <div className="mt-0.5 flex items-baseline gap-1">
              <span className="text-2xl font-semibold tabular-nums">
                {account.balance.toLocaleString()}
              </span>
              <span className="text-sm text-muted-foreground">{t('creditUnit')}</span>
            </div>
          </div>
        </div>
        {onRecharge && (
          <button
            type="button"
            onClick={onRecharge}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-(--zy-primary) px-3 text-xs font-medium text-(--zy-primary-foreground) transition-colors hover:bg-(--zy-primary-hover)"
          >
            <Sparkles className="size-3.5" />
            {t('creditTopUp')}
          </button>
        )}
      </div>

      {account.monthlyAllowance && (
        <div className="mt-4 space-y-2 border-t border-border pt-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">{t('creditMonthlyUsage')}</span>
            <span className="font-medium tabular-nums">
              {account.monthlyUsed?.toLocaleString() ?? 0} / {account.monthlyAllowance.toLocaleString()}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-(--zy-primary) transition-all duration-500"
              style={{ width: `${monthlyPercent}%` }}
            />
          </div>
          {account.nextResetAt && (
            <div className="text-[10px] text-muted-foreground">
              {t('creditNextReset')}: {new Date(account.nextResetAt).toLocaleDateString()}
            </div>
          )}
        </div>
      )}

      <div className="mt-4 grid grid-cols-2 gap-2 border-t border-border pt-3">
        <div className="flex items-center gap-1.5 text-xs">
          <TrendingUp className="size-3.5 text-(--zy-success)" />
          <span className="text-muted-foreground">{t('creditTotalEarned')}</span>
          <span className="ml-auto font-medium tabular-nums">{account.totalEarned.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <TrendingDown className="size-3.5 text-(--zy-destructive)" />
          <span className="text-muted-foreground">{t('creditTotalSpent')}</span>
          <span className="ml-auto font-medium tabular-nums">{account.totalSpent.toLocaleString()}</span>
        </div>
      </div>

      {onViewHistory && (
        <button
          type="button"
          onClick={onViewHistory}
          className="mt-3 flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-(--zy-surface-raised) hover:text-foreground"
        >
          {t('creditViewHistory')}
          <ChevronRight className="size-3.5" />
        </button>
      )}
    </div>
  );
}

export default CreditSummaryCard;
