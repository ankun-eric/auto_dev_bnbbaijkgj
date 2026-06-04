'use client';

// [PRD-AIHOME-CARE-V1 2026-05-27] 首次进入版本选择页
// 关怀模式 / 标准模式 选择 + 跳过 → 默认 standard

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

export default function WelcomeModePage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

  const chooseMode = async (mode: 'care' | 'standard') => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await api.put('/api/care-v1/user-preferences/ui-mode', {
        ui_mode: mode,
        first_choice: true,
      });
    } catch (e) {
      // 即使后端失败也写本地，体验优先
    }
    try {
      localStorage.setItem('ui_mode', mode);
    } catch {}
    if (mode === 'care') {
      router.replace(`${basePath}/care-ai-home`);
    } else {
      router.replace(`${basePath}/`);
    }
  };

  const skip = () => {
    try {
      localStorage.setItem('ui_mode', 'standard');
    } catch {}
    router.replace(`${basePath}/`);
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(180deg, #fff5e8 0%, #f0f6fb 100%)',
        padding: '32px 22px 60px',
        boxSizing: 'border-box',
      }}
    >
      {/* 顶栏品牌 */}
      <div
        style={{
          textAlign: 'center',
          fontSize: 24,
          fontWeight: 800,
          background: 'linear-gradient(90deg,#ff9156,#ff6b3d)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          marginBottom: 20,
        }}
      >
        宾尼小康
      </div>

      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          color: '#3d2e1f',
          marginBottom: 8,
        }}
      >
        您好，欢迎来到宾尼小康 👋
      </div>
      <div style={{ fontSize: 16, color: '#5a4838', marginBottom: 28, lineHeight: 1.6 }}>
        为了让您用得更顺手，请先选择一种使用模式。选完之后，随时可在首页右上角切换。
      </div>

      {/* 关怀模式大卡 */}
      <div
        onClick={() => chooseMode('care')}
        style={{
          background: '#fff',
          borderRadius: 20,
          padding: 22,
          marginBottom: 18,
          boxShadow: '0 6px 24px rgba(255,107,61,.15)',
          border: '2px solid #ff9156',
          position: 'relative',
          cursor: 'pointer',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 14,
            right: 14,
            background: 'linear-gradient(90deg,#ff9156,#ff6b3d)',
            color: '#fff',
            fontSize: 12,
            padding: '3px 10px',
            borderRadius: 12,
            fontWeight: 700,
          }}
        >
          ⭐ 推荐
        </div>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ fontSize: 48, marginRight: 14 }}>👵</div>
          <div style={{ fontSize: 24, fontWeight: 800, color: '#3d2e1f' }}>关怀模式</div>
        </div>
        <div style={{ fontSize: 16, lineHeight: 1.7, color: '#5a4838', marginBottom: 14 }}>
          为长辈量身打造：字更大、按钮更大、语音优先。小康会主动关心您的健康，关键时刻一键求救，让您和家人都安心。
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {['超大字', '超大按钮', '语音优先', 'AI 主动关怀', 'SOS 一键求救'].map((t) => (
            <span
              key={t}
              style={{
                background: '#fff5e8',
                color: '#c95a1d',
                fontSize: 13,
                padding: '5px 12px',
                borderRadius: 16,
                fontWeight: 600,
              }}
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* 标准模式大卡 */}
      <div
        onClick={() => chooseMode('standard')}
        style={{
          background: '#fff',
          borderRadius: 20,
          padding: 22,
          marginBottom: 18,
          boxShadow: '0 4px 16px rgba(91,143,214,.15)',
          border: '2px solid #5b8fd6',
          cursor: 'pointer',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ fontSize: 48, marginRight: 14 }}>🧑‍💼</div>
          <div style={{ fontSize: 24, fontWeight: 800, color: '#2a3a52' }}>标准模式</div>
        </div>
        <div style={{ fontSize: 16, lineHeight: 1.7, color: '#5a4838', marginBottom: 14 }}>
          为熟悉手机操作的用户准备：常规字号、功能完整、数据可视化更丰富，适合自己管理健康或帮长辈打理档案的子女使用。
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {['常规字号', '功能更全', '操作更高效', '数据可视化'].map((t) => (
            <span
              key={t}
              style={{
                background: '#e8f0fb',
                color: '#3865a8',
                fontSize: 13,
                padding: '5px 12px',
                borderRadius: 16,
                fontWeight: 600,
              }}
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* 小康的建议条 */}
      <div
        style={{
          background: '#fff5e8',
          padding: '12px 16px',
          borderRadius: 14,
          fontSize: 14,
          color: '#c95a1d',
          marginBottom: 24,
          lineHeight: 1.6,
        }}
      >
        💡 <b>小康的建议</b>：如果您觉得手机操作有些吃力，或者想给长辈使用，推荐选择「关怀模式」。
      </div>

      {/* 跳过链接 */}
      <div style={{ textAlign: 'center' }}>
        <span
          onClick={skip}
          style={{
            fontSize: 14,
            color: '#999',
            textDecoration: 'underline dashed',
            cursor: 'pointer',
          }}
        >
          暂不选择，先进去看看 →
        </span>
      </div>
    </div>
  );
}
