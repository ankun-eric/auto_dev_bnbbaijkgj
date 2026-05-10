'use client';

import { useEffect } from 'react';
import { bootstrapTheme } from '@/lib/theme-inject';

/**
 * PRD-447 v2 · 主题热注入引导组件
 * 挂载在 RootLayout 中，启动后异步拉取激活主题。
 */
export default function ThemeBootstrap() {
  useEffect(() => {
    bootstrapTheme();
  }, []);
  return null;
}
