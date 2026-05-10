'use client';

import React, { useState } from 'react';
import {
  MedicalCard,
  PrimaryButton,
  TopBar,
  UserBubble,
  HeroDark,
  FnCell,
  RecommendCard,
  FamilyChip,
  RadarChart5,
  FollowupChip,
  ThinkingDots,
  VoiceWave,
} from '@/components/design-system';

/**
 * PRD-447 v2 · 设计系统 12 组件自测页（开发体验 + 像素级回归基础页）。
 * 路由：/design-system-v2-preview
 * 用于 Playwright 截图回归 + 业务页面对照参考。
 */
export default function DesignSystemV2PreviewPage() {
  const [activeFamily, setActiveFamily] = useState('我');

  return (
    <div
      data-testid="bh-ds-preview-root"
      style={{
        background: 'var(--color-bg-page)',
        minHeight: '100vh',
        paddingBottom: 24,
        fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Source Han Sans SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif',
      }}
    >
      <TopBar
        title="方案 A · 组件总览"
        left={<span style={{ color: 'var(--color-brand-700)' }}>‹</span>}
        right={<span style={{ color: 'var(--color-brand-700)' }}>···</span>}
      />

      <div style={{ padding: 16, display: 'grid', gap: 16 }}>
        <section data-testid="section-fn-cell">
          <h3 style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-text-strong)', marginBottom: 12 }}>
            FnCell · 功能宫格（替换 ai-home 多彩渐变）
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            <FnCell icon="🩺" main="AI诊室" sub="智能问诊" />
            <FnCell icon="📋" main="看报告" sub="解读体检报告" />
            <FnCell icon="📁" main="健康档案" sub="查看个人档案" badge="新" />
          </div>
        </section>

        <section data-testid="section-recommend-card">
          <h3 style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-text-strong)', marginBottom: 12 }}>
            RecommendCard · 双色 SVG 推荐卡（屏 ④）
          </h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <RecommendCard icon={<DemoIcon name="heart" />} text="我最近老觉得心慌，要紧吗？" />
            <RecommendCard icon={<DemoIcon name="report" />} text="帮我看看上次体检报告" />
            <RecommendCard icon={<DemoIcon name="med" />} text="高血压药物有什么注意事项？" />
            <RecommendCard icon={<DemoIcon name="bell" />} text="提醒我每天 8 点吃药" />
          </div>
        </section>

        <section data-testid="section-medical-card">
          <h3 style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-text-strong)', marginBottom: 12 }}>
            MedicalCard · 病历卡（左侧 3px brand-400 竖线）
          </h3>
          <MedicalCard>
            <div style={{ fontSize: 'var(--font-size-md)', fontWeight: 600, color: 'var(--color-text-strong)' }}>
              小康建议
            </div>
            <div style={{ fontSize: 'var(--font-size-base)', color: 'var(--color-text-base)', marginTop: 4 }}>
              请保持规律作息，每周三次中等强度运动；饮食注意低盐低脂。
            </div>
          </MedicalCard>
        </section>

        <section data-testid="section-bubble">
          <h3 style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-text-strong)', marginBottom: 12 }}>
            UserBubble · 用户对话气泡
          </h3>
          <div style={{ textAlign: 'right' }}>
            <UserBubble>我最近老觉得心慌，需要去医院吗？</UserBubble>
          </div>
        </section>

        <section data-testid="section-followup">
          <h3 style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-text-strong)', marginBottom: 12 }}>
            FollowupChip · 流式追问 chip（屏 ⑨）
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <FollowupChip text="心慌通常和什么有关？" />
            <FollowupChip text="需要做哪些检查？" />
            <FollowupChip text="是否需要立即就医？" />
          </div>
        </section>

        <section data-testid="section-thinking">
          <h3 style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-text-strong)', marginBottom: 12 }}>
            ThinkingDots · 思考态三圆点
          </h3>
          <div style={{ background: 'var(--color-bg-card)', padding: 12, borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-card)' }}>
            <ThinkingDots /> <span style={{ marginLeft: 8, color: 'var(--color-text-weak)' }}>小康正在思考…</span>
          </div>
        </section>

        <section data-testid="section-voice">
          <h3 style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-text-strong)', marginBottom: 12 }}>
            VoiceWave · 语音声波（屏 ⑥）
          </h3>
          <div style={{ background: 'var(--color-bg-card)', padding: 12, borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-card)' }}>
            <VoiceWave amplitude={0.6} /> <span style={{ marginLeft: 8, color: 'var(--color-text-weak)' }}>正在聆听…</span>
          </div>
        </section>

        <section data-testid="section-family">
          <h3 style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-text-strong)', marginBottom: 12 }}>
            FamilyChip · 家人 chip
          </h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {['我', '爸爸', '妈妈', '孩子'].map(n => (
              <FamilyChip key={n} name={n} active={activeFamily === n} onClick={() => setActiveFamily(n)} />
            ))}
          </div>
        </section>

        <section data-testid="section-radar">
          <h3 style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-text-strong)', marginBottom: 12 }}>
            RadarChart5 · 5 维健康雷达（屏 ⑱）
          </h3>
          <div style={{ background: 'var(--color-bg-card)', padding: 12, borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-card)' }}>
            <RadarChart5
              data={[
                { label: '心脏', value: 78 },
                { label: '睡眠', value: 65 },
                { label: '运动', value: 50 },
                { label: '饮食', value: 72 },
                { label: '心理', value: 88 },
              ]}
              size={240}
            />
          </div>
        </section>

        <section data-testid="section-hero">
          <h3 style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-text-strong)', marginBottom: 12 }}>
            HeroDark · 深色 hero
          </h3>
          <HeroDark>
            <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>体检报告 · 2026-05</div>
            <div style={{ fontSize: 'var(--font-size-base)', opacity: 0.85, marginTop: 6 }}>
              共 23 项指标，3 项轻度异常
            </div>
          </HeroDark>
        </section>

        <section data-testid="section-button">
          <h3 style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-text-strong)', marginBottom: 12 }}>
            PrimaryButton · 主操作按钮
          </h3>
          <div style={{ display: 'flex', gap: 12 }}>
            <PrimaryButton>开始问诊</PrimaryButton>
            <PrimaryButton disabled>禁用态</PrimaryButton>
          </div>
        </section>
      </div>
    </div>
  );
}

const DemoIcon: React.FC<{ name: string }> = ({ name }) => {
  const map: Record<string, string> = {
    heart: 'M12 21s-7-4.5-7-11a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 6.5-7 11-7 11z',
    report: 'M6 3h9l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm9 0v6h6',
    med: 'M5 12a7 7 0 1 0 14 0 7 7 0 0 0-14 0zm2 0h10',
    bell: 'M12 3a6 6 0 0 0-6 6v3l-2 3h16l-2-3V9a6 6 0 0 0-6-6zm-2 17a2 2 0 0 0 4 0',
  };
  const d = map[name] || map.heart;
  return (
    <svg width={24} height={24} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
};
