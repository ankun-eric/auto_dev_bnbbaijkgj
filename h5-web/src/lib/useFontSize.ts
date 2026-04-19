'use client';

import { useState, useEffect, useCallback } from 'react';

export type FontLevel = 'standard' | 'large' | 'xlarge';

interface FontConfig {
  font_switch_enabled: boolean;
  font_default_level: FontLevel;
  font_standard_size: number;
  font_large_size: number;
  font_xlarge_size: number;
}

// v6: 默认字号体系升级为 16/19/22，开关默认 ON
const DEFAULT_FONT_CONFIG: FontConfig = {
  font_switch_enabled: true,
  font_default_level: 'standard',
  font_standard_size: 16,
  font_large_size: 19,
  font_xlarge_size: 22,
};

const FONT_LEVEL_KEY = 'font_level';

function getFontSize(level: FontLevel, config: FontConfig): number {
  switch (level) {
    case 'large':
      return config.font_large_size;
    case 'xlarge':
      return config.font_xlarge_size;
    default:
      return config.font_standard_size;
  }
}

export function useFontSize(fontConfig?: Partial<FontConfig>) {
  const config: FontConfig = { ...DEFAULT_FONT_CONFIG, ...fontConfig };

  const [fontLevel, setFontLevelState] = useState<FontLevel>(() => {
    if (typeof window === 'undefined') return config.font_default_level;
    const saved = localStorage.getItem(FONT_LEVEL_KEY) as FontLevel | null;
    return saved || config.font_default_level;
  });

  const fontSize = getFontSize(fontLevel, config);

  const setFontLevel = useCallback((level: FontLevel) => {
    setFontLevelState(level);
    localStorage.setItem(FONT_LEVEL_KEY, level);
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const saved = localStorage.getItem(FONT_LEVEL_KEY) as FontLevel | null;
    if (!saved) {
      setFontLevelState(config.font_default_level);
    }
  }, [config.font_default_level]);

  return {
    fontLevel,
    fontSize,
    setFontLevel,
    fontSwitchEnabled: config.font_switch_enabled,
  };
}
