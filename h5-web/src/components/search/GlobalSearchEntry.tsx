'use client';

/**
 * [PRD-AI-HOME-V1 2026-05-19] 全局搜索入口胶囊
 *
 * 从原 `(tabs)/home/page.tsx` 顶部抠出的搜索入口组件，复用在 `/services` 等页面顶部。
 *
 * 视觉规格（与旧 home 保持一致）：
 *   - 白底胶囊（圆角 20px、高度 36px、浅灰描边 #E5E5E5）
 *   - 左侧 16x16 灰色放大镜 SVG
 *   - 灰色 placeholder（#999999），文字 14px 截断
 *
 * 交互：
 *   - 点击整个胶囊跳 `/search`（多类目聚合搜索：药品/文章/商品/服务/医生/资讯）
 *   - 输入仅作占位提示，本组件**不**接受真实输入
 *
 * placeholder 取值优先级：
 *   props.placeholder > '搜索健康服务…'
 *
 * 注意：本组件不依赖任何业务 config，由调用方传入 placeholder 即可；
 *      若调用方需从远程 config 取 search_placeholder，请在父组件中读取后传入。
 */

import { useRouter } from 'next/navigation';

interface GlobalSearchEntryProps {
  /** 占位文字。默认「搜索健康服务…」 */
  placeholder?: string;
  /** 自定义点击行为。默认 router.push('/search') */
  onClick?: () => void;
  /** 容器额外样式，用于外层 padding/margin 微调 */
  style?: React.CSSProperties;
  /** 容器额外 className */
  className?: string;
  /** data-testid，便于单测/e2e 定位 */
  testId?: string;
}

export default function GlobalSearchEntry({
  placeholder = '搜索健康服务…',
  onClick,
  style,
  className,
  testId = 'global-search-entry',
}: GlobalSearchEntryProps) {
  const router = useRouter();

  const handleClick = () => {
    if (onClick) {
      onClick();
      return;
    }
    router.push('/search');
  };

  return (
    <div
      role="button"
      aria-label={placeholder}
      data-testid={testId}
      onClick={handleClick}
      className={`flex items-center cursor-pointer ${className || ''}`}
      style={{
        height: 36,
        borderRadius: 20,
        background: '#FFFFFF',
        border: '1px solid #E5E5E5',
        paddingLeft: 12,
        paddingRight: 12,
        ...style,
      }}
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#999999"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <span
        className="ml-2 text-sm truncate"
        style={{ color: '#999999', flex: 1 }}
      >
        {placeholder}
      </span>
    </div>
  );
}
