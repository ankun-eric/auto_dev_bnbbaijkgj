'use client';

/**
 * AiHomeSkeleton —— ai-home 首屏整页骨架屏
 * [PRD-AIHOME-SKELETON-V1 2026-05-19]
 *
 * 用于消除 /ai-home 首屏刷新时的 "默认占位 → 真实数据" 跳变。
 * 像素级还原页面真实结构：
 *   顶部条（汉堡 + 胶囊「咨询人」+ 铃铛）
 *   欢迎语（主标题 + 副标题两行）
 *   健康贴士轮播卡
 *   功能宫格（2 行 × 3 列）
 *   推荐问 3 条胶囊
 *   底部输入框 + 发送按钮
 *
 * 配合 page.tsx 中的 firstScreenStatus 状态机使用：
 *   loading  → 显示骨架屏（shimmer 动画）
 *   failed   → 骨架屏内显示「加载失败，点击重试」卡片
 *   ready    → 真实内容淡入，骨架屏淡出（200ms 交叠）
 *
 * ⚠️ 维护提示：page.tsx 真实 DOM 结构如有改版，请同步更新本组件
 *   以保持像素级一致，避免淡入瞬间元素位移。
 */

import React from 'react';

export interface AiHomeSkeletonProps {
  /** 淡出动画类名：'fade-out' 即开始 200ms 透明度过渡 */
  className?: string;
  /** true 时显示「加载失败，点击重试」卡片 */
  showError?: boolean;
  /** 点击「重试」按钮的回调 */
  onRetry?: () => void;
  /** true 时显示网络异常 UI（顶部状态条 + 中部占位区） */
  isOffline?: boolean;
}

const SkeletonBlock: React.FC<{
  width?: number | string;
  height?: number | string;
  radius?: number | string;
  style?: React.CSSProperties;
  className?: string;
}> = ({ width = '100%', height = 16, radius = 6, style, className }) => (
  <div
    className={`skeleton-shimmer ${className || ''}`}
    style={{
      width,
      height,
      borderRadius: radius,
      ...style,
    }}
  />
);

const SpinIcon: React.FC = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    style={{ animation: 'skeleton-spin 1s linear infinite', flexShrink: 0 }}
  >
    <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.3)" strokeWidth="3" />
    <path d="M12 2a10 10 0 0 1 10 10" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
  </svg>
);

const AiHomeSkeleton: React.FC<AiHomeSkeletonProps> = ({
  className = '',
  showError = false,
  onRetry,
  isOffline = false,
}) => {
  return (
    <div
      className={`ai-home-skeleton ${className}`}
      data-testid="ai-home-skeleton"
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: '#F7F8FA',
        maxWidth: 750,
        margin: '0 auto',
        zIndex: 10,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* 网络异常顶部状态条 */}
      {isOffline && (
        <div
          data-testid="ai-home-skeleton-offline-bar"
          style={{
            width: '100%',
            height: 36,
            background: '#374151',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            flexShrink: 0,
          }}
        >
          <SpinIcon />
          <span style={{ fontSize: 13, color: '#fff', lineHeight: 1 }}>⚠ 网络连接不稳定</span>
        </div>
      )}

      {/* 网络异常中部占位区 */}
      {isOffline && (
        <div
          data-testid="ai-home-skeleton-offline-placeholder"
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            zIndex: 20,
          }}
        >
          <div style={{ fontSize: 64, lineHeight: 1, color: '#CBD5E1', marginBottom: 16 }}>📡</div>
          <div style={{ fontSize: 15, color: '#9CA3AF', marginBottom: 20 }}>暂时无法连接服务器</div>
          <button
            type="button"
            onClick={onRetry}
            data-testid="ai-home-skeleton-offline-retry-btn"
            style={{
              background: 'linear-gradient(135deg, #38BDF8, #0284C7)',
              color: '#fff',
              border: 'none',
              borderRadius: 24,
              height: 44,
              padding: '0 32px',
              fontSize: 15,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            点击重试
          </button>
        </div>
      )}

      {/* 顶部条 48px 高度，与 fixed topbar 完全一致 */}
      <div
        style={{
          position: 'relative',
          height: 'calc(48px + env(safe-area-inset-top))',
          paddingTop: 'env(safe-area-inset-top)',
          width: '100%',
          flexShrink: 0,
        }}
      >
        <div style={{ position: 'relative', height: 48, width: '100%' }}>
          {/* 左：汉堡按钮 圆形 */}
          <SkeletonBlock
            width={22}
            height={17}
            radius={3}
            style={{
              position: 'absolute',
              left: 13,
              top: '50%',
              transform: 'translateY(-50%)',
            }}
          />
          {/* 中：咨询人胶囊 */}
          <SkeletonBlock
            width={140}
            height={28}
            radius={14}
            style={{
              position: 'absolute',
              left: '50%',
              top: '50%',
              transform: 'translate(-50%, -50%)',
            }}
          />
          {/* 右：⋯ 菜单 */}
          <SkeletonBlock
            width={22}
            height={6}
            radius={3}
            style={{
              position: 'absolute',
              right: 13,
              top: '50%',
              transform: 'translateY(-50%)',
            }}
          />
        </div>
      </div>

      {/* 中部可滚动区 */}
      <div
        style={{
          flex: 1,
          overflow: 'hidden',
          padding: '8px 16px 0 16px',
          position: 'relative',
        }}
      >
        {/* 欢迎语区 */}
        <div style={{ padding: '12px 0 16px 0' }}>
          <SkeletonBlock width="60%" height={22} radius={6} style={{ marginBottom: 10 }} />
          <SkeletonBlock width="40%" height={14} radius={6} />
        </div>

        {/* 健康贴士卡 ≈130px 高 */}
        <SkeletonBlock
          width="100%"
          height={130}
          radius={12}
          style={{ marginBottom: 16 }}
        />

        {/* 功能宫格 2 行 × 3 列 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
            gap: 12,
            marginBottom: 16,
          }}
        >
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              style={{
                background: '#fff',
                borderRadius: 12,
                padding: '12px 8px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: 76,
              }}
            >
              <SkeletonBlock
                width={32}
                height={32}
                radius={16}
                style={{ marginBottom: 8 }}
              />
              <SkeletonBlock width="70%" height={12} radius={4} />
            </div>
          ))}
        </div>

        {/* 推荐问 3 条胶囊 */}
        <div
          style={{
            display: 'flex',
            gap: 8,
            marginBottom: 16,
            overflow: 'hidden',
          }}
        >
          <SkeletonBlock width={110} height={36} radius={18} />
          <SkeletonBlock width={130} height={36} radius={18} />
          <SkeletonBlock width={100} height={36} radius={18} />
        </div>

        {/* 失败态卡片 */}
        {showError && (
          <div
            data-testid="ai-home-skeleton-error"
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              background: '#fff',
              borderRadius: 12,
              padding: '24px 32px',
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              minWidth: 220,
              zIndex: 20,
            }}
          >
            <div style={{ fontSize: 32, marginBottom: 8, lineHeight: 1 }}>⚠️</div>
            <div
              style={{
                fontSize: 15,
                color: '#1F2937',
                marginBottom: 16,
                fontWeight: 500,
              }}
            >
              加载失败
            </div>
            <button
              type="button"
              onClick={onRetry}
              style={{
                background: '#0EA5E9',
                color: '#fff',
                border: 'none',
                borderRadius: 20,
                padding: '8px 24px',
                fontSize: 14,
                cursor: 'pointer',
                fontWeight: 500,
              }}
              data-testid="ai-home-skeleton-retry-btn"
            >
              点击重试
            </button>
          </div>
        )}
      </div>

      {/* 底部输入框 + 发送按钮 */}
      <div
        style={{
          padding: '8px 12px calc(8px + env(safe-area-inset-bottom)) 12px',
          background: '#F7F8FA',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexShrink: 0,
          borderTop: '1px solid rgba(0,0,0,0.04)',
        }}
      >
        <SkeletonBlock height={40} radius={20} style={{ flex: 1 }} />
        <SkeletonBlock width={56} height={40} radius={20} />
      </div>
    </div>
  );
};

export default AiHomeSkeleton;
