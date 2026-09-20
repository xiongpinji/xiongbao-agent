import { useTheme } from '../../theme/ThemeContext';

interface ThemeBrandLogoProps {
  /** Size in pixels (default: 28) */
  size?: number;
  className?: string;
}

/**
 * Renders the current theme's brand logo if available.
 * Falls back to nothing if the theme has no logo defined.
 *
 * @example
 * <ThemeBrandLogo size={28} className="mr-2" />
 */
export function ThemeBrandLogo({ size = 28, className }: ThemeBrandLogoProps) {
  const { currentTheme } = useTheme();

  if (!currentTheme?.branding?.logo) {
    return null;
  }

  return (
    <img
      src={currentTheme.branding.logo}
      alt={currentTheme.branding.productName || 'Logo'}
      width={size}
      height={size}
      className={className}
      style={{ objectFit: 'contain' }}
    />
  );
}
