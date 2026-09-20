import { useState } from 'react';
import { i18nService } from '../../services/i18n';
import { Coins, Search, Filter, Download, Plus, Minus, RotateCcw, Gift } from 'lucide-react';
import { cn } from '@shared/lib/utils';
import type { CreditTransaction } from './CreditSummaryCard';

export type { CreditTransaction };

export interface CreditHistoryProps {
  transactions: CreditTransaction[];
  loading?: boolean;
  onExport?: () => void;
  onFilter?: (filter: { type?: string; keyword?: string; dateRange?: string }) => void;
  onClose?: () => void;
  className?: string;
}

const TYPE_ICONS: Record<CreditTransaction['type'], React.ComponentType<{ className?: string }>> = {
  earn: Plus,
  spend: Minus,
  recharge: Coins,
  gift: Gift,
  refund: RotateCcw,
};

const TYPE_COLORS: Record<CreditTransaction['type'], string> = {
  earn: 'text-(--zy-transaction-earn-foreground) bg-(--zy-transaction-earn-background)',
  spend: 'text-(--zy-transaction-spend-foreground) bg-(--zy-transaction-spend-background)',
  recharge: 'text-(--zy-transaction-recharge-foreground) bg-(--zy-transaction-recharge-background)',
  gift: 'text-(--zy-transaction-gift-foreground) bg-(--zy-transaction-gift-background)',
  refund: 'text-(--zy-transaction-refund-foreground) bg-(--zy-transaction-refund-background)',
};

export function CreditHistory({
  transactions,
  loading = false,
  onExport,
  onFilter,
  className,
}: CreditHistoryProps) {
  const { t } = { t: (key: string) => i18nService.t(key) };
  const [keyword, setKeyword] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  const filtered = transactions.filter((tx) => {
    if (typeFilter !== 'all' && tx.type !== typeFilter) return false;
    if (keyword && !tx.description.toLowerCase().includes(keyword.toLowerCase())) return false;
    return true;
  });

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setKeyword(value);
    onFilter?.({ type: typeFilter === 'all' ? undefined : typeFilter, keyword: value });
  };

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    setTypeFilter(value);
    onFilter?.({ type: value === 'all' ? undefined : value, keyword });
  };

  return (
    <div className={cn('flex flex-col', className)}>
      <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={keyword}
            onChange={handleSearch}
            placeholder={t('creditHistorySearch')}
            className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm outline-none transition-colors focus:border-(--zy-primary) focus:ring-2 focus:ring-(--zy-primary-muted)"
          />
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Filter className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <select
              value={typeFilter}
              onChange={handleTypeChange}
              className="h-9 appearance-none rounded-lg border border-border bg-background pl-7 pr-7 text-sm outline-none transition-colors focus:border-(--zy-primary)"
            >
              <option value="all">{t('creditHistoryFilterAll')}</option>
              <option value="earn">{t('creditHistoryTypeEarn')}</option>
              <option value="spend">{t('creditHistoryTypeSpend')}</option>
              <option value="recharge">{t('creditHistoryTypeRecharge')}</option>
              <option value="gift">{t('creditHistoryTypeGift')}</option>
              <option value="refund">{t('creditHistoryTypeRefund')}</option>
            </select>
          </div>
          {onExport && (
            <button
              type="button"
              onClick={onExport}
              title={t('creditHistoryExport')}
              aria-label={t('creditHistoryExport')}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-background px-3 text-sm transition-colors hover:bg-(--zy-surface-raised)"
            >
              <Download className="size-3.5" />
              <span className="hidden sm:inline">{t('creditHistoryExport')}</span>
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
            {t('commonLoading')}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Coins className="mb-3 size-12 text-muted-foreground/30" />
            <p className="text-sm text-muted-foreground">{t('creditHistoryEmpty')}</p>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {filtered.map((tx) => {
              const Icon = TYPE_ICONS[tx.type];
              const colorClass = TYPE_COLORS[tx.type];
              const isPositive = tx.type === 'earn' || tx.type === 'recharge' || tx.type === 'refund';
              return (
                <li key={tx.id} className="flex items-center gap-3 p-4 hover:bg-(--zy-surface-raised)">
                  <div className={cn('flex size-9 shrink-0 items-center justify-center rounded-full', colorClass)}>
                    <Icon className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-medium">{tx.description}</p>
                      {tx.category && (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          {tx.category}
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {new Date(tx.timestamp).toLocaleString()}
                    </p>
                  </div>
                  <div className={cn(
                    'shrink-0 text-right text-sm font-semibold tabular-nums',
                    isPositive ? 'text-(--zy-success)' : 'text-(--zy-destructive)',
                  )}>
                    {isPositive ? '+' : '−'}{Math.abs(tx.amount).toLocaleString()}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

export default CreditHistory;
