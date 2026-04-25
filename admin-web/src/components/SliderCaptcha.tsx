'use client';

/**
 * SliderCaptcha - 滑块拼图验证码组件
 *
 * Bug 修复 V1.0 / 2026-04-25：替代旧字符验证码
 * - 商家 H5 / 商家 PC 三端共用本组件，响应式适配
 * - 默认 PC 尺寸 320x160；H5 端可显式传 mode="mobile" 强制 280x140
 * - 通过后回调 onSuccess(captcha_token)
 * - 内置：换一张、锁定倒计时、加载态、成功 / 失败动画
 *
 * 注意：组件接收 apiClient 注入（h5-web 使用 axios api 单例；admin-web 同样可注入）。
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';

export interface SliderCaptchaApiClient {
  get: <T = any>(url: string) => Promise<T>;
  post: <T = any>(url: string, data: any) => Promise<T>;
}

export interface SliderCaptchaProps {
  apiClient: SliderCaptchaApiClient;
  onSuccess: (token: string) => void;
  onReset?: () => void;
  mode?: 'auto' | 'pc' | 'mobile';
  className?: string;
}

interface ChallengeData {
  challenge_id: string;
  bg_image_base64: string;
  puzzle_image_base64: string;
  puzzle_y: number;
  bg_width: number;
  bg_height: number;
  puzzle_size: number;
}

interface VerifyResult {
  ok: boolean;
  captcha_token?: string;
  expires_in?: number;
  reason?: string;
  locked_seconds?: number;
}

type Status = 'idle' | 'loading' | 'ready' | 'sliding' | 'verifying' | 'success' | 'fail' | 'locked';

const REASON_TEXT: Record<string, string> = {
  position_mismatch: '没对准缺口，请再试一次',
  trail_invalid: '滑动轨迹异常，请正常拖动',
  challenge_expired: '验证已过期，请刷新重试',
  locked: '失败次数过多，请稍后再试',
};

export const SliderCaptcha: React.FC<SliderCaptchaProps> = ({
  apiClient,
  onSuccess,
  onReset,
  mode = 'auto',
  className,
}) => {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [containerWidth, setContainerWidth] = useState<number>(320);
  const [challenge, setChallenge] = useState<ChallengeData | null>(null);
  const [status, setStatus] = useState<Status>('idle');
  const [tip, setTip] = useState<string>('');
  const [sliderX, setSliderX] = useState<number>(0);
  const [lockedSeconds, setLockedSeconds] = useState<number>(0);
  const trailRef = useRef<Array<{ x: number; y: number; t: number }>>([]);
  const draggingRef = useRef<boolean>(false);
  const startXRef = useRef<number>(0);
  const startTRef = useRef<number>(0);
  const startScreenXRef = useRef<number>(0);

  const detectMobile = useCallback((): boolean => {
    if (mode === 'pc') return false;
    if (mode === 'mobile') return true;
    if (typeof window === 'undefined') return false;
    return window.innerWidth <= 600;
  }, [mode]);

  const resolveSize = useCallback(() => {
    const isMobile = detectMobile();
    if (typeof window === 'undefined') return isMobile ? 280 : 320;
    const max = isMobile ? 320 : 360;
    const min = 240;
    const w = Math.min(Math.max(window.innerWidth - 40, min), max);
    return w;
  }, [detectMobile]);

  useEffect(() => {
    const onResize = () => setContainerWidth(resolveSize());
    onResize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [resolveSize]);

  const issue = useCallback(async () => {
    setStatus('loading');
    setTip('正在加载...');
    setSliderX(0);
    trailRef.current = [];
    try {
      const data = await apiClient.get<ChallengeData>('/api/captcha/slider/issue');
      setChallenge(data);
      setStatus('ready');
      setTip('请按住滑块，拖动至缺口位置');
    } catch (e: any) {
      setStatus('fail');
      setTip('加载失败，点击换一张');
    }
  }, [apiClient]);

  useEffect(() => {
    issue();
  }, [issue]);

  // 锁定倒计时
  useEffect(() => {
    if (status !== 'locked' || lockedSeconds <= 0) return;
    const timer = setInterval(() => {
      setLockedSeconds((s) => {
        if (s <= 1) {
          clearInterval(timer);
          setStatus('idle');
          issue();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [status, lockedSeconds, issue]);

  const isMobile = detectMobile();
  const renderHeight = isMobile ? Math.round(containerWidth * (140 / 280)) : Math.round(containerWidth * (160 / 320));
  const sliderHandleSize = 40;
  const maxSlideX = containerWidth - sliderHandleSize;

  // 当前服务端坐标系下的 x：把组件容器内的相对位置缩放回 320 像素（后端基准）
  const toServerX = useCallback((containerX: number): number => {
    if (!challenge) return 0;
    return Math.round((containerX / maxSlideX) * (challenge.bg_width - challenge.puzzle_size));
  }, [challenge, maxSlideX]);

  const onDragStart = useCallback((screenX: number) => {
    if (status !== 'ready' && status !== 'fail') return;
    if (status === 'fail') {
      // 重新拉一张
      issue();
      return;
    }
    draggingRef.current = true;
    startXRef.current = sliderX;
    startTRef.current = Date.now();
    startScreenXRef.current = screenX;
    trailRef.current = [{ x: 0, y: 0, t: 0 }];
    setStatus('sliding');
    setTip('对准缺口后松手');
  }, [status, sliderX, issue]);

  const onDragMove = useCallback((screenX: number, screenY: number) => {
    if (!draggingRef.current) return;
    const dx = screenX - startScreenXRef.current;
    const newX = Math.min(Math.max(0, startXRef.current + dx), maxSlideX);
    setSliderX(newX);
    trailRef.current.push({
      x: newX,
      y: (screenY - (trailRef.current[0] as any)?.absY || 0),
      t: Date.now() - startTRef.current,
    });
  }, [maxSlideX]);

  const submitVerify = useCallback(async () => {
    if (!challenge) return;
    setStatus('verifying');
    setTip('验证中...');
    const serverX = toServerX(sliderX);
    try {
      const result = await apiClient.post<VerifyResult>('/api/captcha/slider/verify', {
        challenge_id: challenge.challenge_id,
        x: serverX,
        trail: trailRef.current,
      });
      if (result.ok && result.captcha_token) {
        setStatus('success');
        setTip('验证通过');
        onSuccess(result.captcha_token);
      } else if (result.reason === 'locked') {
        setStatus('locked');
        const sec = result.locked_seconds || 60;
        setLockedSeconds(sec);
        setTip(`失败过多，请等待 ${sec} 秒`);
      } else {
        setStatus('fail');
        setTip(REASON_TEXT[result.reason || ''] || '验证失败，点击换一张');
        // 失败后自动拉新挑战，1.2s 后
        setTimeout(() => issue(), 1200);
      }
    } catch (e) {
      setStatus('fail');
      setTip('网络异常，点击换一张');
    }
  }, [challenge, sliderX, toServerX, apiClient, onSuccess, issue]);

  const onDragEnd = useCallback(() => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    submitVerify();
  }, [submitVerify]);

  // 鼠标事件
  useEffect(() => {
    const move = (e: MouseEvent) => onDragMove(e.clientX, e.clientY);
    const up = () => onDragEnd();
    if (status === 'sliding') {
      window.addEventListener('mousemove', move);
      window.addEventListener('mouseup', up);
      return () => {
        window.removeEventListener('mousemove', move);
        window.removeEventListener('mouseup', up);
      };
    }
  }, [status, onDragMove, onDragEnd]);

  // 触摸事件
  useEffect(() => {
    const move = (e: TouchEvent) => {
      if (e.touches[0]) {
        e.preventDefault();
        onDragMove(e.touches[0].clientX, e.touches[0].clientY);
      }
    };
    const up = () => onDragEnd();
    if (status === 'sliding') {
      window.addEventListener('touchmove', move, { passive: false });
      window.addEventListener('touchend', up);
      window.addEventListener('touchcancel', up);
      return () => {
        window.removeEventListener('touchmove', move);
        window.removeEventListener('touchend', up);
        window.removeEventListener('touchcancel', up);
      };
    }
  }, [status, onDragMove, onDragEnd]);

  const handleRefresh = () => {
    if (status === 'locked' || status === 'verifying') return;
    onReset?.();
    issue();
  };

  const puzzleScale = challenge ? containerWidth / challenge.bg_width : 1;
  const puzzleScreenSize = challenge ? challenge.puzzle_size * puzzleScale : 50;
  const puzzleScreenY = challenge ? challenge.puzzle_y * puzzleScale : 0;

  const sliderTrackColor =
    status === 'success' ? '#52c41a' : status === 'fail' ? '#ff4d4f' : status === 'locked' ? '#faad14' : '#1677ff';
  const handleColor =
    status === 'success' ? '#52c41a' : status === 'fail' ? '#ff4d4f' : status === 'locked' ? '#faad14' : '#fff';

  return (
    <div className={className} ref={wrapperRef} style={{ width: containerWidth, userSelect: 'none' }}>
      {/* 图片区 */}
      <div
        style={{
          position: 'relative',
          width: containerWidth,
          height: renderHeight,
          borderRadius: 8,
          overflow: 'hidden',
          background: '#f0f2f5',
          border: '1px solid #d9d9d9',
        }}
      >
        {challenge && (
          <>
            <img
              src={challenge.bg_image_base64}
              alt="captcha-bg"
              draggable={false}
              style={{ width: '100%', height: '100%', display: 'block' }}
            />
            {/* 缺块拼图 */}
            <img
              src={challenge.puzzle_image_base64}
              alt="captcha-puzzle"
              draggable={false}
              style={{
                position: 'absolute',
                top: puzzleScreenY,
                left: sliderX,
                width: puzzleScreenSize,
                height: puzzleScreenSize,
                pointerEvents: 'none',
                filter: status === 'success' ? 'drop-shadow(0 0 4px #52c41a)' : 'drop-shadow(0 1px 3px rgba(0,0,0,.4))',
                transition: status === 'fail' ? 'left 0.4s' : 'none',
              }}
            />
            {/* 刷新按钮 */}
            <div
              onClick={handleRefresh}
              title="换一张"
              style={{
                position: 'absolute',
                top: 6,
                right: 6,
                background: 'rgba(0,0,0,0.45)',
                color: '#fff',
                width: 28,
                height: 28,
                borderRadius: 14,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: status === 'locked' || status === 'verifying' ? 'not-allowed' : 'pointer',
                fontSize: 14,
                opacity: status === 'locked' || status === 'verifying' ? 0.4 : 1,
              }}
            >
              ↻
            </div>
          </>
        )}
        {!challenge && status === 'loading' && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#666',
              fontSize: 12,
            }}
          >
            加载中...
          </div>
        )}
      </div>
      {/* 提示文字 */}
      <div
        style={{
          height: 22,
          marginTop: 6,
          fontSize: 12,
          color:
            status === 'success' ? '#52c41a' : status === 'fail' || status === 'locked' ? '#ff4d4f' : '#666',
          textAlign: 'center',
        }}
      >
        {status === 'locked' ? `失败过多，剩余 ${lockedSeconds} 秒` : tip}
      </div>
      {/* 滑块条 */}
      <div
        style={{
          position: 'relative',
          marginTop: 6,
          height: sliderHandleSize,
          background: '#f5f5f5',
          borderRadius: sliderHandleSize / 2,
          border: '1px solid #e0e0e0',
        }}
      >
        {/* 已拖动轨迹高亮 */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            height: '100%',
            width: sliderX + sliderHandleSize,
            background: sliderTrackColor + '22',
            borderTopLeftRadius: sliderHandleSize / 2,
            borderBottomLeftRadius: sliderHandleSize / 2,
            transition: status === 'fail' ? 'width 0.4s' : 'none',
          }}
        />
        {/* 文字提示 */}
        {status === 'ready' && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 13,
              color: '#999',
              pointerEvents: 'none',
            }}
          >
            按住滑块，拖动至缺口位置
          </div>
        )}
        {/* 拖动手柄 */}
        <div
          onMouseDown={(e) => onDragStart(e.clientX)}
          onTouchStart={(e) => {
            if (e.touches[0]) onDragStart(e.touches[0].clientX);
          }}
          style={{
            position: 'absolute',
            top: 0,
            left: sliderX,
            width: sliderHandleSize,
            height: sliderHandleSize,
            borderRadius: sliderHandleSize / 2,
            background: handleColor,
            border: `1px solid ${sliderTrackColor}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: status === 'locked' || status === 'verifying' || status === 'success' ? 'not-allowed' : 'grab',
            boxShadow: '0 2px 4px rgba(0,0,0,.15)',
            color: status === 'success' || status === 'fail' || status === 'locked' ? '#fff' : '#666',
            fontSize: 16,
            transition: status === 'fail' ? 'left 0.4s' : 'none',
            touchAction: 'none',
          }}
        >
          {status === 'success' ? '✓' : status === 'fail' ? '✗' : status === 'locked' ? '⏱' : '→'}
        </div>
      </div>
    </div>
  );
};

export default SliderCaptcha;
