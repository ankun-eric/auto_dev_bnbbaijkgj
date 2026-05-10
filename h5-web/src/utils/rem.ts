/**
 * PRD-447 v2 · 双档 rem 适配
 * 基准：375 / 390（移动端主流），最大 750（避免桌面端字号无限放大）
 * 使用：在 RootLayout 通过 useEffect 调用 setupRem()
 */
export function setupRem() {
  if (typeof window === 'undefined' || typeof document === 'undefined') return () => {};
  const set = () => {
    const w = Math.min(window.innerWidth, 750);
    // 双档：>=390 用 390 基准；否则用 375 基准
    const base = w >= 390 ? 390 : 375;
    document.documentElement.style.fontSize = `${(w / base) * 16}px`;
  };
  set();
  window.addEventListener('resize', set);
  window.addEventListener('orientationchange', set);
  return () => {
    window.removeEventListener('resize', set);
    window.removeEventListener('orientationchange', set);
  };
}
