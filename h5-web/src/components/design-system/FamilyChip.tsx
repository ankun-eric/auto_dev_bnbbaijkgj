'use client';
import React from 'react';

export interface FamilyChipProps {
  name: string;
  active?: boolean;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
  testId?: string;
}

export const FamilyChip: React.FC<FamilyChipProps> = ({
  name,
  active = false,
  onClick,
  className = '',
  style,
  testId = 'bh-family-chip',
}) => {
  return (
    <span
      className={`bh-family-chip ${active ? 'active' : ''} ${className}`}
      onClick={onClick}
      style={style}
      data-testid={testId}
      data-active={active ? '1' : '0'}
    >
      {name}
    </span>
  );
};
