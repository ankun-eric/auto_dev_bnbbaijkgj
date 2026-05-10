'use client';
import React from 'react';

export interface VoiceWaveProps {
  /** 0~1，振幅倍数（语音输入响度） */
  amplitude?: number;
  className?: string;
  testId?: string;
}

/**
 * 语音声波 + 实时转写（屏 ⑥）。
 * 振幅响应 amplitude（用 CSS 变量 --bh-voice-amp 暴露给样式自定义场景）。
 */
export const VoiceWave: React.FC<VoiceWaveProps> = ({
  amplitude = 1,
  className = '',
  testId = 'bh-voice-wave',
}) => {
  const amp = Math.max(0, Math.min(1, amplitude));
  const style: React.CSSProperties = { ['--bh-voice-amp' as any]: amp };
  return (
    <span className={`bh-voice-wave ${className}`} style={style} data-testid={testId} aria-label="语音输入中">
      <span />
      <span />
      <span />
      <span />
      <span />
    </span>
  );
};
