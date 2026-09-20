import { useTheme } from '../../theme/ThemeContext';

interface ThemeBrandMascotProps {
  /** Size in pixels (default: 140) */
  size?: number;
  className?: string;
}

/**
 * Renders the current theme's brand mascot if available.
 * Falls back to nothing if the theme has no mascot defined.
 *
 * @example
 * <ThemeBrandMascot size={140} className="mx-auto" />
 */
export function ThemeBrandMascot({ size = 140, className }: ThemeBrandMascotProps) {
  const { currentTheme } = useTheme();

  if (!currentTheme?.branding?.mascot) {
    return null;
  }

  return (
    <img
      src={currentTheme.branding.mascot}
      alt={currentTheme.branding.productName || 'Mascot'}
      width={size}
      height={size}
      className={className}
      style={{ objectFit: 'contain' }}
    />
  );
}
