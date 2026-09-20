import React, { useState } from 'react';
import { Menu, Settings, ChevronLeft } from 'lucide-react';
import { cn } from '@shared/lib/utils';
import { MobileSheet } from './Responsive';
import { ThemeBrandLogo } from '../brand/ThemeBrandLogo';
import { i18nService } from '../../services/i18n';

export interface MobileChatLayoutProps {
  /** 左侧抽屉内容（会话列表、导航等） */
  drawerContent: React.ReactNode;
  /** 右侧设置抽屉 */
  settingsContent?: React.ReactNode;
  /** 中间主体内容 */
  children: React.ReactNode;
  /** 顶部标题 */
  title?: React.ReactNode;
  /** 返回按钮回调（移动端二级页面用） */
  onBack?: () => void;
}

/**
 * 移动端聊天布局：顶部固定 AppBar + 底部抽屉式导航。
 * 桌面端 (≥768px) 直接渲染 children，不做任何包裹。
 */
export function MobileChatLayout({
  drawerContent,
  settingsContent,
  children,
  title,
  onBack,
}: MobileChatLayoutProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Localised strings. Falls back to the supplied Chinese string when a
  // translation is missing so the mobile UI never regresses to a raw key.
  const localize = (key: string, fallback: string): string => {
    const value = i18nService.t(key);
    return value && value !== key ? value : fallback;
  };
  const brandTitle = localize('mobileDrawerTitle', '熊宝 Agent');
  const settingsTitle = localize('mobileSettingsTitle', '设置');
  const backLabel = localize('mobileBack', '返回');
  const menuLabel = localize('mobileMenuToggle', '打开导航');
  const settingsLabel = localize('mobileSettingsToggle', '打开设置');

  return (
    <>
      {/* 移动端专用 AppBar (md 以下显示) */}
      <div className="sticky top-0 z-30 flex h-12 items-center gap-2 border-b border-border bg-background/95 px-3 backdrop-blur-sm md:hidden">
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            aria-label={backLabel}
            className="-ml-1 flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-(--zy-surface-raised)"
          >
            <ChevronLeft className="size-5" />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label={menuLabel}
            className="-ml-1 flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-(--zy-surface-raised)"
          >
            <Menu className="size-5" />
          </button>
        )}
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <ThemeBrandLogo size={20} />
          <span className="truncate text-sm font-semibold">{title}</span>
        </div>
        {settingsContent && (
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            aria-label={settingsLabel}
            className="flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-(--zy-surface-raised)"
          >
            <Settings className="size-4" />
          </button>
        )}
      </div>

      {/* 主体 */}
      <div className="md:contents">{children}</div>

      {/* 移动端导航抽屉 */}
      <MobileSheet
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={
          <div className="flex items-center gap-2">
            <ThemeBrandLogo size={22} />
            <span>{brandTitle}</span>
          </div>
        }
      >
        {drawerContent}
      </MobileSheet>

      {/* 移动端设置抽屉 */}
      {settingsContent && (
        <MobileSheet
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          title={title ?? settingsTitle}
          snapPoints={[70, 92]}
        >
          {settingsContent}
        </MobileSheet>
      )}
    </>
  );
}

export interface MobileBottomNavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  active?: boolean;
  badge?: number | string;
}

export interface MobileBottomNavProps {
  items: MobileBottomNavItem[];
  className?: string;
}

export function MobileBottomNav({ items, className }: MobileBottomNavProps) {
  return (
    <nav
      className={cn(
        'fixed inset-x-0 bottom-0 z-30 flex items-center justify-around border-t border-border bg-background/95 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-1.5 backdrop-blur-sm md:hidden',
        className,
      )}
    >
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={item.onClick}
          className={cn(
            'relative flex min-h-[44px] min-w-[64px] flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-2 py-1 text-[10px] transition-colors',
            item.active
              ? 'text-(--zy-primary)'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <div className="relative">
            {item.icon}
            {item.badge && (
              <span className="absolute -right-2 -top-1 flex min-w-[16px] items-center justify-center rounded-full bg-(--zy-destructive) px-1 text-[9px] font-medium text-(--zy-destructive-foreground)">
                {item.badge}
              </span>
            )}
          </div>
          <span className="truncate">{item.label}</span>
        </button>
      ))}
    </nav>
  );
}

export default MobileChatLayout;
