import { useEffect, useState } from 'react';
import { ChevronUp } from 'lucide-react';
import { cn } from '@shared/lib/utils';

export interface ScrollToTopProps {
  /** 滚动多少 px 后显示按钮 */
  threshold?: number;
  className?: string;
}

/**
 * 浮动「回到顶部」按钮，主要为移动端优化。
 */
export function ScrollToTop({ threshold = 400, className }: ScrollToTopProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > threshold);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [threshold]);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <button
      type="button"
      onClick={scrollToTop}
      aria-label="回到顶部"
      className={cn(
        'fixed bottom-6 right-6 z-40 flex size-11 items-center justify-center rounded-full border border-border bg-surface/95 shadow-lg backdrop-blur-sm transition-all duration-300 hover:border-(--zy-primary) hover:bg-(--zy-primary-muted) hover:text-(--zy-primary) md:bottom-8 md:right-8',
        visible
          ? 'pointer-events-auto translate-y-0 opacity-100'
          : 'pointer-events-none translate-y-4 opacity-0',
        className,
      )}
    >
      <ChevronUp className="size-5" />
    </button>
  );
}

export default ScrollToTop;
