import { useState } from 'react';
import { i18nService } from '../../services/i18n';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@shared/components/ui/dialog';
import { Coins, Sparkles, Check, Loader2 } from 'lucide-react';
import { cn } from '@shared/lib/utils';

export interface RechargePlan {
  id: string;
  credits: number;
  bonus?: number;
  priceCents: number;
  currency?: string;
  popular?: boolean;
  description?: string;
}

export interface RechargeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plans: RechargePlan[];
  currentBalance?: number;
  onPurchase?: (planId: string) => Promise<void> | void;
  loading?: boolean;
}

export function RechargeDialog({
  open,
  onOpenChange,
  plans,
  currentBalance = 0,
  onPurchase,
  loading = false,
}: RechargeDialogProps) {
  const { t } = { t: (key: string) => i18nService.t(key) };
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handlePurchase = async () => {
    if (!selectedPlan || !onPurchase) return;
    setSubmitting(true);
    try {
      await onPurchase(selectedPlan);
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  const formatPrice = (cents: number, currency = 'CNY') => {
    return new Intl.NumberFormat('zh-CN', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(cents / 100);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="size-5 text-(--zy-primary)" />
            {t('creditRechargeFormTitle')}
          </DialogTitle>
          {currentBalance > 0 && (
            <div className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
              <Coins className="size-4 text-(--zy-primary)" />
              <span>
                {t('creditRechargeCurrentBalance')}{' '}
                <strong className="font-semibold text-foreground">
                  {currentBalance.toLocaleString()}
                </strong>
              </span>
            </div>
          )}
        </DialogHeader>

        <div className="grid gap-3 py-2 sm:grid-cols-2">
          {plans.map((plan) => {
            const total = plan.credits + (plan.bonus ?? 0);
            const isSelected = selectedPlan === plan.id;
            return (
              <button
                key={plan.id}
                type="button"
                onClick={() => setSelectedPlan(plan.id)}
                className={cn(
                  'relative flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition-all',
                  isSelected
                    ? 'border-(--zy-primary) bg-(--zy-primary-muted) ring-2 ring-(--zy-primary-muted)'
                    : 'border-border bg-surface hover:border-(--zy-primary-muted) hover:bg-(--zy-surface-raised)',
                )}
              >
                {plan.popular && (
                  <span className="absolute -top-2 right-3 rounded-full bg-(--zy-primary) px-2 py-0.5 text-[10px] font-medium text-(--zy-primary-foreground)">
                    {t('creditRechargePopular')}
                  </span>
                )}
                <div className="flex w-full items-center justify-between">
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-semibold tabular-nums">
                      {plan.credits.toLocaleString()}
                    </span>
                    <span className="text-xs text-muted-foreground">{t('creditUnit')}</span>
                    {plan.bonus ? (
                      <span className="ml-1 text-xs font-medium text-(--zy-primary)">
                        +{plan.bonus.toLocaleString()}
                      </span>
                    ) : null}
                  </div>
                  {isSelected && (
                    <Check className="size-4 text-(--zy-primary)" />
                  )}
                </div>
                {plan.description && (
                  <p className="text-xs text-muted-foreground">{plan.description}</p>
                )}
                <div className="mt-1 flex w-full items-center justify-between border-t border-border/50 pt-2">
                  <span className="text-xs text-muted-foreground">
                    {t('creditRechargeTotalReceived')} {total.toLocaleString()}
                  </span>
                  <span className="text-lg font-semibold tabular-nums text-(--zy-primary)">
                    {formatPrice(plan.priceCents, plan.currency)}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        <DialogFooter className="gap-2">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="inline-flex h-9 items-center rounded-lg border border-border bg-background px-4 text-sm transition-colors hover:bg-(--zy-surface-raised)"
          >
            {t('common.cancel')}
          </button>
          <button
            type="button"
            onClick={handlePurchase}
            disabled={!selectedPlan || submitting || loading}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-(--zy-primary) px-4 text-sm font-medium text-(--zy-primary-foreground) transition-colors hover:bg-(--zy-primary-hover) disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting && <Loader2 className="size-3.5 animate-spin" />}
            {submitting ? t('common.processing') : t('creditRechargeConfirm')}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default RechargeDialog;
