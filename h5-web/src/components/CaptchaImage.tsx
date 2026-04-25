'use client';

/**
 * CaptchaImage - 4 位字符图形验证码组件
 *
 * v1.4 / 2026-04-26 视觉规格回退到 v1.0
 *
 * 同时供：商家 PC 后台（mode='pc'，固定 160×60，与 v1.0 老版完全一致）
 *       商家 H5 后台（mode='mobile'，按屏宽 50% 自适应，宽度上下限 120 ~ 220）
 *
 * - CSS 显示尺寸 = 物理像素 = 160 × 60（取消 v1.3 的 2× 高 DPI 渲染）
 * - 后端字号回归 38px，字符撑满画布约 60%~65%（与 v1.0 历史视觉完全一致）
 * - 1:1 渲染，移动端按比例自适应（保持现有 120~220 区间）
 * - 可点击刷新；加载失败显示「加载失败，点击重试」占位
 * - 监听 resize / orientationchange 重新计算尺寸（mobile）
 *
 * 历史版本：
 * - v1.0：160×60 / 38px 老版（用户认可、长期使用的视觉）
 * - v1.1~v1.2：曾尝试放大画布，因布局错位被回退
 * - v1.3：保留画布 160×60，但启用 2× DPI（实际 320×120）+ 字号 96，被反馈"看起来没变大"
 * - v1.4：彻底回退到 v1.0 视觉规格，画布、字号均回归 v1.0 老版样式
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
