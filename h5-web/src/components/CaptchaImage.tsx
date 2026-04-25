'use client';

/**
 * CaptchaImage - 4 位字符图形验证码组件
 *
 * v1.2 / 2026-04-25 仅字号放大版
 *
 * 同时供：商家 PC 后台（mode='pc'，固定 160×60，与线上原版一致）
 *       商家 H5 后台（mode='mobile'，按屏宽 50% 自适应，宽度上下限 120 ~ 220）
 *
 * - 后端画布 160×60 / 2× 物理像素 / 字号 96px，字符显示明显大于旧版（38px）
 * - 本轮只放大字号、不动画布
 * - 可点击刷新；加载失败显示「加载失败，点击重试」占位
 * - 监听 resize / orientationchange 重新计算尺寸（mobile）
 */
import React, { useCallback, useEffect, useImperativeHandle, useState } from 'react';
import { fetchCaptchaImage } from '@/lib/captcha';

export interface CaptchaImageRef {
  refresh: () => void;
  reset: () => void;
}

export interface CaptchaImageProps {
  onChange: (captchaId: string) => void;
  mode?: 'pc' | 'mobile';
  width?: number;
  height?: number;
  refreshKey?: number;
}

const PC_W = 160;
const PC_H = 60;
const ASPECT = PC_W / PC_H; // 8/3

function calcMobileSize(): { w: number; h: number } {
  if (typeof window === 'undefined') return { w: 160, h: 60 };
  const sw = window.innerWidth || 375;
  let w = Math.round(sw * 0.5);
  if (w < 120) w = 120;
  if (w > 220) w = 220;
  const h = Math.round(w / ASPECT);
  return { w, h };
}

const CaptchaImage = React.forwardRef<CaptchaImageRef, CaptchaImageProps>(function CaptchaImage(
  { onChange, mode = 'pc', width, height, refreshKey = 0 },
  ref,
) {
  const [imgSrc, setImgSrc] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<boolean>(false);
  const [size, setSize] = useState<{ w: number; h: number }>(() => {
    if (mode === 'mobile') return calcMobileSize();
    return { w: width || PC_W, h: height || PC_H };
  });

  useEffect(() => {
    if (mode !== 'mobile') return;
    const handler = () => setSize(calcMobileSize());
    window.addEventListener('resize', handler);
    window.addEventListener('orientationchange', handler);
    return () => {
      window.removeEventListener('resize', handler);
      window.removeEventListener('orientationchange', handler);
    };
  }, [mode]);

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
        width: size.w,
        height: size.h,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f5f5f5',
        border: '1px solid #d9d9d9',
        borderRadius: 4,
        overflow: 'hidden',
        cursor: loading ? 'progress' : 'pointer',
        userSelect: 'none',
        flexShrink: 0,
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
