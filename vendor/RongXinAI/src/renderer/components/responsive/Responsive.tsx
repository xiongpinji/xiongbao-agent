import React from 'react';
import { cn } from '@shared/lib/utils';

export type DeviceType = 'mobile' | 'tablet' | 'desktop';

export interface ResponsiveProps {
  children: React.ReactNode;
  className?: string;
  /** Tailwind breakpoints via min-width */
  minWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
}

/**
 * 仅在指定断点及以上显示
 * @example <Show minWidth="md">桌面端</Show>
 */
export function Show({ children, className, minWidth = 'md' }: ResponsiveProps) {
  return (
    <div className={cn(`hidden ${minWidth}:block`, className)}>
      {children}
    </div>
  );
}

export interface HideProps extends ResponsiveProps {}

export function Hide({ children, className, minWidth = 'md' }: HideProps) {
  return (
    <div className={cn(`${minWidth}:hidden`, className)}>
      {children}
    </div>
  );
}

export interface MobileOnlyProps {
  children: React.ReactNode;
  className?: string;
}

export function MobileOnly({ children, className }: MobileOnlyProps) {
  return <div className={cn('md:hidden', className)}>{children}</div>;
}

export interface DesktopOnlyProps {
  children: React.ReactNode;
  className?: string;
}

export function DesktopOnly({ children, className }: DesktopOnlyProps) {
  return <div className={cn('hidden md:block', className)}>{children}</div>;
}

export interface ResponsiveContainerProps {
  children: React.ReactNode;
  className?: string;
  /** Padding per breakpoint */
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

/**
 * Responsive container with safe-area padding for mobile browsers.
 */
export function ResponsiveContainer({
  children,
  className,
  padding = 'md',
}: ResponsiveContainerProps) {
  const paddingMap = {
    none: '',
    sm: 'px-3 py-3',
    md: 'px-4 py-4 sm:px-6 sm:py-5',
    lg: 'px-4 py-5 sm:px-8 sm:py-6',
  } as const;

  return (
    <div
      className={cn(
        'mx-auto w-full',
        paddingMap[padding],
        'pb-[max(1rem,env(safe-area-inset-bottom))]',
        'pt-[max(0.5rem,env(safe-area-inset-top))]',
        className,
      )}
    >
      {children}
    </div>
  );
}

export interface MobileSheetProps {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  children: React.ReactNode;
  /** Snap points in vh, default ['65', '92'] */
  snapPoints?: number[];
}

import { X } from 'lucide-react';

export function MobileSheet({
  open,
  onClose,
  title,
  children,
  snapPoints = [65, 92],
}: MobileSheetProps) {
  if (!open) return null;
  const initialSnap = snapPoints[0];
  return (
    <div className="fixed inset-0 z-50 md:hidden">
      <div
        className="absolute inset-0 backdrop-blur-sm transition-opacity"
        style={{ backgroundColor: 'var(--zy-overlay-scrim)' }}
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        className="absolute inset-x-0 bottom-0 flex max-h-[92vh] flex-col rounded-t-2xl bg-background shadow-2xl animate-in slide-in-from-bottom duration-300"
        style={{ height: `${initialSnap}vh` }}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex-1 truncate text-base font-semibold">{title}</div>
          <button
            type="button"
            onClick={onClose}
            className="ml-2 flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-(--zy-surface-raised)"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto overscroll-contain">{children}</div>
      </div>
    </div>
  );
}

export interface ResponsiveGridProps {
  children: React.ReactNode;
  className?: string;
  cols?: {
    mobile?: number;
    tablet?: number;
    desktop?: number;
  };
  gap?: 'sm' | 'md' | 'lg';
}

export function ResponsiveGrid({
  children,
  className,
  cols = { mobile: 1, tablet: 2, desktop: 3 },
  gap = 'md',
}: ResponsiveGridProps) {
  const gapMap = {
    sm: 'gap-2',
    md: 'gap-4',
    lg: 'gap-6',
  } as const;

  // Tailwind cannot extract dynamic class names (grid-cols-${n}); allow-list the
  // expected 1..6 columns so the JIT compiler keeps them in the bundle.
  const allowed = [1, 2, 3, 4, 5, 6] as const;
  const safe = (n: number | undefined, fallback: number) =>
    allowed.includes(n as 1 | 2 | 3 | 4 | 5 | 6) ? (n as 1 | 2 | 3 | 4 | 5 | 6) : fallback;

  const colClasses = [
    `grid-cols-${safe(cols.mobile, 1)}`,
    `sm:grid-cols-${safe(cols.tablet, 2)}`,
    `lg:grid-cols-${safe(cols.desktop, 3)}`,
  ].join(' ');

  return (
    <div className={cn('grid', gapMap[gap], colClasses, className)}>
      {children}
    </div>
  );
}

export interface TouchTargetProps {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
  ariaLabel?: string;
}

/**
 * 触控友好的按钮包装器：保证最小 44×44 命中区域
 */
export function TouchTarget({ children, onClick, className, ariaLabel }: TouchTargetProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className={cn(
        'relative inline-flex min-h-[44px] min-w-[44px] items-center justify-center',
        className,
      )}
    >
      {children}
    </button>
  );
}
