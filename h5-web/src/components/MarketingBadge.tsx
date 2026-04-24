/**
 * 商品功能优化 v1.0 - 营销角标公共组件
 *
 * 展示规则（R6）：
 * - 输入 badges 多个时，按 limited > hot > new > recommend 仅渲染最高优先级 1 个
 * - 无 badge 时不渲染（返回 null）
 * - 位置贴齐父容器左上角，父容器需 position:relative
 */

export type MarketingBadgeValue = 'limited' | 'hot' | 'new' | 'recommend';

const BADGE_CONF: Record<
  MarketingBadgeValue,
  { label: string; bg: string }
> = {
  limited: { label: '限时', bg: '#FF4D4F' },
  hot: { label: '热销', bg: '#FF8C1A' },
  new: { label: '新品', bg: '#1890FF' },
  recommend: { label: '推荐', bg: '#52C41A' },
};

const PRIORITY: MarketingBadgeValue[] = ['limited', 'hot', 'new', 'recommend'];

export function pickTopBadge(
  badges?: string[] | null,
): MarketingBadgeValue | null {
  if (!Array.isArray(badges) || badges.length === 0) return null;
  for (const p of PRIORITY) {
    if (badges.includes(p)) return p;
  }
  return null;
}

interface Props {
  badges?: string[] | null;
  size?: 'sm' | 'md';
  // 是否绝对定位到左上角（默认 true）。false 时可内联使用。
  floating?: boolean;
}

export default function MarketingBadge({
  badges,
  size = 'md',
  floating = true,
}: Props) {
  const top = pickTopBadge(badges);
  if (!top) return null;
  const conf = BADGE_CONF[top];

  const fontSize = size === 'sm' ? 9 : 11;
  const padding = size === 'sm' ? '1px 4px' : '2px 6px';

  const style: React.CSSProperties = {
    background: conf.bg,
    color: '#fff',
    fontSize,
    padding,
    lineHeight: 1.2,
    fontWeight: 600,
    borderRadius: '0 0 6px 0',
    letterSpacing: 0.5,
    whiteSpace: 'nowrap',
  };
  if (floating) {
    style.position = 'absolute';
    style.top = 0;
    style.left = 0;
    style.zIndex = 2;
    style.pointerEvents = 'none';
  }

  return <span style={style}>{conf.label}</span>;
}
