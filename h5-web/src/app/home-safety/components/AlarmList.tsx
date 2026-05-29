'use client';

/**
 * [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29]
 * 居家安全 - 报警记录列表组件
 */
import { useCallback, useEffect, useState } from 'react';
import api from '@/lib/api';

interface AlarmItem {
  id: number;
  device_type: number;
  device_type_label: string;
  device_sn: string;
  device_remark?: string | null;
  member_id?: number | null;
  member_name?: string | null;
  alarm_at: string;
  handle_status: number;
  read_status: number;
  notify_ai_call_status?: string | null;
  notify_phone_mask?: string | null;
}

interface Props {
  memberId: number | null;
  /** 是否当前为"本人"Tab（用于决定是否隐藏触发成员） */
  isSelfActive: boolean;
}

const DEVICE_TYPE_COLOR: Record<number, { bg: string; fg: string; label: string }> = {
  1: { bg: '#FFEBEE', fg: '#E53935', label: '紧急呼叫器' },
  2: { bg: '#FFF3E0', fg: '#FB8C00', label: '烟雾报警器' },
  7: { bg: '#FFFDE7', fg: '#FBC02D', label: '水位报警器' },
};

function formatRelative(s?: string | null): string {
  if (!s) return '';
  try {
    const d = new Date(s);
    const now = new Date();
    const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
    if (diff < 86400 * 2) {
      const hh = String(d.getHours()).padStart(2, '0');
      const mm = String(d.getMinutes()).padStart(2, '0');
      return `昨天 ${hh}:${mm}`;
    }
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  } catch {
    return s;
  }
}

function formatAbsolute(s?: string | null): string {
  if (!s) return '';
  try {
    const d = new Date(s);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${y}-${m}-${day} ${hh}:${mm}`;
  } catch {
    return s;
  }
}

export default function AlarmList({ memberId, isSelfActive }: Props) {
  const [items, setItems] = useState<AlarmItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const SIZE = 20;

  const load = useCallback(
    async (pageNum: number, reset: boolean) => {
      if (memberId == null) return;
      setLoading(true);
      try {
        const r: any = await api.get(
          `/api/home_safety/alarms?member_id=${memberId}&page=${pageNum}&size=${SIZE}`,
        );
        const arr: AlarmItem[] = (r as any)?.items ?? (r as any)?.data?.items ?? [];
        setItems((prev) => (reset ? arr : prev.concat(arr)));
        setHasMore(arr.length >= SIZE);
        setPage(pageNum);
      } catch (e: any) {
        console.error('[AlarmList] load fail:', e?.message);
      } finally {
        setLoading(false);
      }
    },
    [memberId],
  );

  useEffect(() => {
    load(1, true);
  }, [load]);

  if (memberId == null) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: '#999', fontSize: 13 }}>
        请先选择家庭成员
      </div>
    );
  }

  if (!loading && items.length === 0) {
    return (
      <div
        style={{
          padding: '48px 24px',
          textAlign: 'center',
          color: '#999',
          fontSize: 13,
          background: '#fff',
          borderRadius: 12,
          margin: 16,
        }}
      >
        <div style={{ fontSize: 48, marginBottom: 12 }}>🛡️</div>
        <div style={{ marginBottom: 4 }}>暂无报警记录</div>
        <div style={{ fontSize: 12, color: '#BBB' }}>希望永远用不到这里 🙏</div>
      </div>
    );
  }

  return (
    <div style={{ padding: 16 }}>
      {items.map((a) => {
        const tag = DEVICE_TYPE_COLOR[a.device_type] || {
          bg: '#EEE',
          fg: '#999',
          label: a.device_type_label || '未知',
        };
        const statusInfo =
          a.handle_status === 1
            ? { dot: '#43A047', label: '已处理' }
            : a.handle_status === 2
              ? { dot: '#9E9E9E', label: '已忽略' }
              : { dot: '#E53935', label: '未处理' };
        const remark = a.device_remark || '';
        const phoneMask = a.notify_phone_mask || '';
        const showNotify = a.notify_ai_call_status === 'sent' || a.notify_ai_call_status === 'ok';
        return (
          <div
            key={a.id}
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 14,
              marginBottom: 12,
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            }}
            onClick={() => {
              try {
                alert(`报警详情\n时间：${formatAbsolute(a.alarm_at)}\n设备：${tag.label} ${remark || '未命名'}`);
              } catch {}
            }}
          >
            {/* 第 1 行：设备 Tag + 状态点 + 时间 + 触发成员（非本人 Tab） */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 6,
                gap: 8,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
                <span
                  style={{
                    background: tag.bg,
                    color: tag.fg,
                    fontSize: 12,
                    padding: '2px 8px',
                    borderRadius: 10,
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {tag.label}
                </span>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 12,
                    color: statusInfo.dot,
                    fontWeight: 500,
                    whiteSpace: 'nowrap',
                  }}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: statusInfo.dot,
                      display: 'inline-block',
                    }}
                  />
                  {statusInfo.label}
                </span>
              </div>
              <span
                title={formatAbsolute(a.alarm_at)}
                style={{
                  fontSize: 12,
                  color: '#999',
                  whiteSpace: 'nowrap',
                }}
              >
                {formatRelative(a.alarm_at)}
              </span>
            </div>

            {/* 第 2 行：设备备注名 */}
            <div
              style={{
                fontSize: 14,
                color: remark ? '#333' : '#BBB',
                fontWeight: remark ? 500 : 400,
                marginBottom: 4,
              }}
            >
              {remark || '未命名'}
              {!isSelfActive && a.member_name ? (
                <span
                  style={{
                    marginLeft: 8,
                    fontSize: 11,
                    background: '#E3F2FD',
                    color: '#1F6FE6',
                    padding: '1px 6px',
                    borderRadius: 6,
                    fontWeight: 500,
                  }}
                >
                  {a.member_name}名下
                </span>
              ) : null}
            </div>

            {/* 第 3 行：外呼通知（仅已通知时显示） */}
            {showNotify && phoneMask ? (
              <div
                style={{
                  fontSize: 12,
                  color: '#43A047',
                  marginBottom: 4,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <span>✓</span>
                <span>已外呼通知紧急联系人 {phoneMask}</span>
              </div>
            ) : null}

            {/* 第 4 行：SN 副信息 */}
            <div style={{ fontSize: 11, color: '#BBB' }}>SN：{a.device_sn}</div>
          </div>
        );
      })}
      {hasMore ? (
        <div
          onClick={() => (loading ? null : load(page + 1, false))}
          style={{
            textAlign: 'center',
            color: '#1F8FE6',
            fontSize: 13,
            padding: '12px 0',
            cursor: loading ? 'default' : 'pointer',
          }}
        >
          {loading ? '加载中…' : '加载更多'}
        </div>
      ) : items.length > 0 ? (
        <div style={{ textAlign: 'center', color: '#BBB', fontSize: 12, padding: '12px 0' }}>
          没有更多了
        </div>
      ) : null}
    </div>
  );
}
