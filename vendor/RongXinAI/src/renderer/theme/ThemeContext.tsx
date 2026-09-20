import React, { createContext, useContext, useState } from 'react';
import { ThemeManager } from './engine/theme-manager';
import type { ThemeDefinition } from './themes/types';

interface ThemeContextValue {
  currentTheme: ThemeDefinition | null;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

interface ThemeProviderProps {
  manager: ThemeManager;
  children: React.ReactNode;
}

export function ThemeProvider({ manager, children }: ThemeProviderProps) {
  // ThemeManager lacks a public subscribe hook; re-render when the React tree
  // owns the manager by polling every 500ms. Real product code would consume
  // the manager in a higher-level store; this context is a thin bridge.
  const [, force] = useState(0);
  React.useEffect(() => {
    const id = window.setInterval(() => force((n) => n + 1), 500);
    return () => window.clearInterval(id);
  }, []);

  const currentTheme = manager.getTheme() ?? null;

  const value = React.useMemo<ThemeContextValue>(() => ({ currentTheme }), [currentTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    return { currentTheme: null };
  }
  return ctx;
}
