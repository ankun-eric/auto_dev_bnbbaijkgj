'use client';
import React from 'react';

export interface PrimaryButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  style?: React.CSSProperties;
  type?: 'button' | 'submit' | 'reset';
  testId?: string;
}

export const PrimaryButton: React.FC<PrimaryButtonProps> = ({
  children,
  onClick,
  disabled = false,
  className = '',
  style,
  type = 'button',
  testId = 'bh-primary-button',
}) => {
  return (
    <button
      type={type}
      className={`bh-btn-primary ${className}`}
      onClick={onClick}
      disabled={disabled}
      style={style}
      data-testid={testId}
    >
      {children}
    </button>
  );
};
