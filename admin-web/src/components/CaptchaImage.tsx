'use client';

/**
 * CaptchaImage - 4 位字符图形验证码组件（PC 端）
 *
 * v1.2 / 2026-04-25 仅字号放大版
 * - 显示尺寸 160 × 60 CSS 像素（与线上原版一致，本轮只放大字号、不动画布）
 * - 后端按 2× 物理像素渲染（320 × 120）+ 字号 96px，浏览器下采样后字符清晰锐利
 * - 字号在视觉上较旧版（38px）显著加大，便于肉眼识别
 * - 可点击刷新；加载失败显示「加载失败，点击重试」占位
 */
import React, { useCallback, useEffect, useImperativeHandle, useState } from 'react';
import { fetchCaptchaImage } from '@/lib/captcha';

export interface CaptchaImageRef {
  refresh: () => void;
  reset: () => void;
}

export interface CaptchaImageProps {
  onChange: (captchaId: string) => void;
  width?: number;
  height?: number;
  refreshKey?: number; // 父组件改变此值即触发重刷新
}

const CaptchaImage = React.forwardRef<CaptchaImageRef, CaptchaImageProps>(function CaptchaImage(
  { onChange, width = 160, height = 60, refreshKey = 0 },
  ref,
) {
  const [imgSrc, setImgSrc] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<boolean>(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const res = await fetchCaptchaImage();
      setImgSrc(res.image_base64);
      onChange(res.captcha_id);
    } catch (e) {
      setError(true);
      setImgSrc('');
      onChange('');
    } finally {
      setLoading(false);
    }
  }, [onChange]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  useImperativeHandle(ref, () => ({
    refresh: load,
    reset: load,
  }));

  return (
    <div
      onClick={() => !loading && load()}
      title="点击刷新验证码"
      role="button"
      aria-label="点击刷新验证码"
      style={{
        width,
        height,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f5f5f5',
        border: '1px solid #d9d9d9',
        borderRadius: 4,
        overflow: 'hidden',
        cursor: loading ? 'progress' : 'pointer',
        userSelect: 'none',
        transition: 'opacity 0.15s',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.opacity = '0.85';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.opacity = '1';
      }}
    >
      {error ? (
        <span style={{ color: '#999', fontSize: 12 }}>加载失败，点击重试</span>
      ) : loading && !imgSrc ? (
        <span style={{ color: '#999', fontSize: 12 }}>加载中…</span>
      ) : (
        <img
          src={imgSrc}
          alt="点击刷新验证码"
          style={{ width: '100%', height: '100%', display: 'block' }}
          draggable={false}
        />
      )}
    </div>
  );
});

export default CaptchaImage;
