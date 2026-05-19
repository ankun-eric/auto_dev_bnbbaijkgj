'use client';

/**
 * [PRD-BELL-UNIFIED-V1 2026-05-19] AI 首页"今日待办"胶囊（方案 B + 视觉细节方案 D）
 *
 * 横向胶囊，一行两胶囊，紧凑型：
 *   - 白底 + 浅描边 + 左侧 3px 品牌色竖条 + 轻阴影
 *   - 用药竖条 #0EA5E9（天蓝）；订单竖条 #F59E0B（橙）
 *   - 高度 ~60px，内边距 12px 16px，圆角 12px
 *   - 主标题 14/600，数字 16/700
 *   - 数字 = 0 时显示「0 条待服 / 0 条待办」，不显示红点
 *   - 数字 > 0 显示静态红点；含紧急事项时脉动
 *   - 整块胶囊可点击；点击后打开铃铛抽屉
 *   - 反馈动效：scale(0.97) + transition 100ms
 *
 * 数据源：复用 /api/medication-reminder/badge（无需新增接口）。
 * 拉取时机：首次渲染 + 每次返回前台（visibility）+ 全局事件总线广播。
 */

import { useCallback, useEffect, useState } from 'react';
import api from '@/lib/api';
import { subscribeBellEvent } from '@/lib/bell-event-bus';

interface BadgeShape {
  total: number;
  medication: { count: number; has_urgent: boolean };
  order: { count: number; has_urgent: boolean };
}

const ZERO: BadgeShape = {
  total: 0,
  medication: { count: 0, has_urgent: false },
  order: { count: 0, has_urgent: false },
};

interface Props {
  onOpenDrawer: () => void;
}

export default function TodayTodoCapsules({ onOpenDrawer }: Props) {
  const [badge, setBadge] = useState<BadgeShape>(ZERO);
  const [pressedKey, setPressedKey] = useState<string | null>(null);

  const fetchBadge = useCallback(async () => {
    try {
      const res: any = await api.get('/api/medication-reminder/badge');
      const data = (res?.data ?? res) || {};
      const medCount = Number(
        data?.medication?.count ?? data?.medication_unchecked ?? 0,
      );
      const medUrgent = Boolean(data?.medication?.has_urgent ?? false);
      const orderCount = Number(
        data?.order?.count ?? data?.appointment_pending ?? 0,
      );
      const orderUrgent = Boolean(data?.order?.has_urgent ?? false);
      const total = Number(data?.total ?? medCount + orderCount);
      setBadge({
        total: Number.isFinite(total) ? total : 0,
        medication: {
          count: Number.isFinite(medCount) ? medCount : 0,
          has_urgent: medUrgent,
        },
        order: {
          count: Number.isFinite(orderCount) ? orderCount : 0,
          has_urgent: orderUrgent,
        },
      });
    } catch {
      setBadge(ZERO);
    }
  }, []);

  useEffect(() => {
    fetchBadge();
  }, [fetchBadge]);

  // 全局事件总线 + visibilitychange 双保险
  useEffect(() => {
    const unsub = subscribeBellEvent('badge:refresh', () => fetchBadge());
    const onVisible = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
        fetchBadge();
      }
    };
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisible);
    }
    return () => {
      unsub();
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisible);
      }
    };
  }, [fetchBadge]);

  const handleClick = (key: string) => {
    setPressedKey(key);
    setTimeout(() => setPressedKey(null), 120);
    onOpenDrawer();
  };

  const renderCapsule = (
    key: 'medication' | 'order',
    barColor: string,
    icon: string,
    title: string,
    count: number,
    countSuffix: string,
    urgent: boolean,
  ) => {
    const pressed = pressedKey === key;
    return (
      <button
        type="button"
        data-testid={`bell-capsule-${key}`}
        data-count={count}
        data-urgent={urgent ? '1' : '0'}
        onClick={() => handleClick(key)}
        style={{
          flex: 1,
          minWidth: 0,
          height: 60,
          display: 'flex',
          alignItems: 'stretch',
          background: '#FFFFFF',
          border: '1px solid #E5E7EB',
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(15,23,42,.04)',
          overflow: 'hidden',
          cursor: 'pointer',
          padding: 0,
          transform: pressed ? 'scale(0.97)' : 'scale(1.0)',
          transition: 'transform 100ms ease-out',
        }}
      >
        {/* 左侧 3px 品牌色竖条 */}
        <span
          aria-hidden
          style={{ width: 3, alignSelf: 'stretch', background: barColor, flexShrink: 0 }}
        />
        <span
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            padding: '0 16px',
            minWidth: 0,
            position: 'relative',
          }}
        >
          <span
            aria-hidden
            style={{
              fontSize: 22,
              lineHeight: 1,
              marginRight: 10,
              flexShrink: 0,
            }}
          >
            {icon}
          </span>
          <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1, textAlign: 'left' }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: '#111827', lineHeight: 1.2 }}>
              {title}
            </span>
            <span
              style={{
                fontSize: 16,
                fontWeight: 700,
                color: '#111827',
                marginTop: 4,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                lineHeight: 1,
              }}
            >
              <span>
                {count} {countSuffix}
              </span>
              {count > 0 && (
                <span
                  data-testid={`bell-capsule-${key}-dot`}
                  data-urgent={urgent ? '1' : '0'}
                  className={urgent ? 'bell-capsule-dot-pulse' : ''}
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 9999,
                    background: '#EF4444',
                    display: 'inline-block',
                    flexShrink: 0,
                  }}
                />
              )}
            </span>
          </span>
        </span>
      </button>
    );
  };

  return (
    <div
      data-testid="ai-home-today-todo-capsules"
      style={{
        display: 'flex',
        gap: 12,
        margin: '16px 0',
        width: '100%',
      }}
    >
      {renderCapsule(
        'medication',
        '#0EA5E9',
        '💊',
        '今日用药',
        badge.medication.count,
        '条待服',
        badge.medication.has_urgent,
      )}
      {renderCapsule(
        'order',
        '#F59E0B',
        '🛒',
        '待处理订单',
        badge.order.count,
        '条待办',
        badge.order.has_urgent,
      )}
      <style jsx global>{`
        @keyframes bell-capsule-dot-pulse-kf {
          0% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.4); opacity: 0.6; }
          100% { transform: scale(1); opacity: 1; }
        }
        .bell-capsule-dot-pulse {
          animation: bell-capsule-dot-pulse-kf 1.2s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
