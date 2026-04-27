'use client';

import { THEME } from '@/lib/theme';

interface RecommendCard {
  tag: string;
  text: string;
}

interface RecommendCardsProps {
  items: RecommendCard[];
  onSelect: (text: string) => void;
}

export default function RecommendCards({ items, onSelect }: RecommendCardsProps) {
  if (!items.length) return null;

  return (
    <div
      className="flex gap-2 overflow-x-auto py-2 px-1"
      style={{ scrollbarWidth: 'none' }}
    >
      {items.map((item, i) => (
        <div
          key={i}
          className="flex-shrink-0 px-3 py-2 rounded-xl cursor-pointer active:opacity-70"
          style={{
            background: THEME.primaryLight,
            border: `1px solid ${THEME.divider}`,
            maxWidth: 200,
          }}
          onClick={() => onSelect(item.text)}
        >
          <span className="text-xs font-medium" style={{ color: THEME.primary }}>#{item.tag}</span>
          <div className="text-xs mt-0.5 line-clamp-2" style={{ color: THEME.textPrimary }}>{item.text}</div>
        </div>
      ))}
    </div>
  );
}
