import React, { createContext, useContext, useMemo, useState } from 'react';

export const THEMES = [
  {
    id: 'light',
    label: 'Light',
    hint: 'Navy and purple',
    swatches: ['#142A43', '#8C66D6', '#F3F6F8'],
  },
  {
    id: 'dark',
    label: 'Dark',
    hint: 'Navy and blue',
    swatches: ['#0C1626', '#2563EB', '#122032'],
  },
] as const;

export type ThemeId = (typeof THEMES)[number]['id'];

const STORAGE_KEY = 'lumeneios_theme';

export function isThemeId(value: string | null): value is ThemeId {
  return THEMES.some((theme) => theme.id === value);
}

export function readStoredTheme(): ThemeId {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    const theme: ThemeId = saved === 'dark' || saved === 'midnight' ? 'dark' : 'light';
    if (saved !== theme) localStorage.setItem(STORAGE_KEY, theme);
    return theme;
  } catch {
    return 'light';
  }
}

export function applyTheme(theme: ThemeId) {
  document.documentElement.dataset.theme = theme;
}

applyTheme(readStoredTheme());

interface ThemeContextValue {
  theme: ThemeId;
  setTheme: (theme: ThemeId) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<ThemeId>(readStoredTheme);

  const setTheme = (next: ThemeId) => {
    applyTheme(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* storage can be unavailable in private contexts */
    }
    setThemeState(next);
  };

  const value = useMemo(() => ({ theme, setTheme }), [theme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}

export interface ChartPalette {
  border: string;
  card: string;
  secondary: string;
  ink: string;
  accent: string;
  muted: string;
}

function channel(style: CSSStyleDeclaration, name: string, fallback: string) {
  const value = style.getPropertyValue(name).trim();
  return value ? `rgb(${value})` : fallback;
}

export function useChartPalette(): ChartPalette {
  const { theme } = useTheme();

  return useMemo(() => {
    const style = getComputedStyle(document.documentElement);
    return {
      border: channel(style, '--surface-border', '#E1E7ED'),
      card: channel(style, '--surface-card', '#FFFFFF'),
      secondary: channel(style, '--content-secondary', '#667085'),
      ink: channel(style, '--ink-navy-800', '#142A43'),
      accent: channel(style, '--bg-teal-500', '#16A085'),
      muted: channel(style, '--content-muted', '#98A2B3'),
    };
  }, [theme]);
}
