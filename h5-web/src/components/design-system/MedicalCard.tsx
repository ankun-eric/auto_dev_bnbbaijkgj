'use client';
import React from 'react';

export interface MedicalCardProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  onClick?: () => void;
  testId?: string;
}

export const MedicalCard: React.FC<MedicalCardProps> = ({
  children,
  className = '',
  style,
  onClick,
  testId = 'bh-medical-card',
}) => {
  return (
    <div
      className={`bh-card-medical ${className}`}
      style={style}
      onClick={onClick}
      data-testid={testId}
    >
      {children}
    </div>
  );
};
