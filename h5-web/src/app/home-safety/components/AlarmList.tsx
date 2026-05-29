'use client';

/**
 * [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] v1.0
 * [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-V2 2026-05-29] v2.0
 *   - Bug 4：移除点击卡片触发的 alert()
 *   - Bug 4：新增独立一行的秒级精确时间 "🕐 YYYY-MM-DD HH:mm:ss"
 *   - Bug 4：未处理状态新增「标记已处理」按钮 + 二次确认弹窗
 *   - 视觉：左侧 6px 色块条 + 状态胶囊 + 备注名升级为主标题 16px/600 + SN 下沉
 *
 * 居家安全 - 报警记录列表组件
 */
import { useCallback, useEffect, useState } from 'react';
import api from '@/lib/api';
import { showToast } from '@/lib/toast-unified';

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

const DEVICE_TYPE_COLOR: Record<number, { bg: string; fg: string; bar: string; label: string }> = {
  1: { bg: '#FFEBEE', fg: '#E53935', bar: '#E53935', label: '紧急呼叫器' },
  2: { bg: '#FFF3E0', fg: '#FB8C00', bar: '#FB8C00', label: '烟雾报警器' },
  7: { bg: '#FFFDE7', fg: '#F9A825', bar: '#FBC02D', label: '水位报警器' },
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

/** 秒级精确时间 "YYYY-MM-DD HH:mm:ss" */
function formatAbsoluteSecond(s?: string | null): string {
  if (!s) return '';
  try {
    const d = new Date(s);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `${y}-${m}-${day} ${hh}:${mm}:${ss}`;
  } catch {
    return s;
  }
}

export default function AlarmList({ memberId, isSelfActive }: Props) {
  const [items, setItems] = useState<AlarmItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [resolveTarget, setResolveTarget] = useState<AlarmItem | null>(null);
  const [resolving, setResolving] = useState(false);
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

  const doResolve = async () => {
    if (!resolveTarget) return;
    setResolving(true);
    try {
      // PRD 锁定接口：PATCH /api/home_safety/alarms/{id}/resolve（幂等）
      await api.patch(`/api/home_safety/alarms/${resolveTarget.id}/resolve`, {});
      showToast('已标记为已处理');
      setItems((prev) =>
        prev.map((it) =>
          it.id === resolveTarget.id ? { ...it, handle_status: 1, read_status: 1 } : it,
        ),
      );
      setResolveTarget(null);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '处理失败，请稍后重试');
    } finally {
      setResolving(false);
    }
  };

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
    <div style={{ padding: 16 }} data-testid="alarm-list">
      {items.map((a) => {
        const tag = DEVICE_TYPE_COLOR[a.device_type] || {
          bg: '#EEE',
          fg: '#999',
          bar: '#BDBDBD',
          label: a.device_type_label || '未知',
        };
        // 状态胶囊：未处理（红）/ 已处理（绿）/ 已忽略（灰）
        const statusPill =
          a.handle_status === 1
            ? { dot: '#43A047', bg: '#E8F5E9', fg: '#2E7D32', label: '已处理' }
            : a.handle_status === 2
              ? { dot: '#9E9E9E', bg: '#F5F5F5', fg: '#616161', label: '已忽略' }
              : { dot: '#E53935', bg: '#FFEBEE', fg: '#C62828', label: '未处理' };
        const remark = a.device_remark || '';
        const phoneMask = a.notify_phone_mask || '';
        const showNotify = a.notify_ai_call_status === 'sent' || a.notify_ai_call_status === 'ok';
        const isPending = a.handle_status === 0;
        return (
          <div
            key={a.id}
            data-testid={`alarm-card-${a.id}`}
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 0,
              marginBottom: 12,
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
              display: 'flex',
              overflow: 'hidden',
              position: 'relative',
            }}
          >
            {/* 左侧 6px 色块条 */}
            <div
              style={{
                width: 6,
                flexShrink: 0,
                background: tag.bar,
              }}
              data-testid={`alarm-bar-${a.id}`}
            />
            <div style={{ flex: 1, padding: 14, minWidth: 0 }}>
              {/* 第 1 行：设备 Tag + 状态胶囊 + 相对时间 */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 8,
                  marginBottom: 6,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    flex: 1,
                    minWidth: 0,
                    flexWrap: 'wrap',
                  }}
                >
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
                    data-testid={`alarm-status-pill-${a.id}`}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      fontSize: 12,
                      background: statusPill.bg,
                      color: statusPill.fg,
                      padding: '2px 8px',
                      borderRadius: 10,
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: statusPill.dot,
                        display: 'inline-block',
                      }}
                    />
                    {statusPill.label}
                  </span>
                  {!isSelfActive && a.member_name ? (
                    <span
                      style={{
                        fontSize: 11,
                        background: '#E3F2FD',
                        color: '#1F6FE6',
                        padding: '1px 6px',
                        borderRadius: 6,
                        fontWeight: 500,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {a.member_name}名下
                    </span>
                  ) : null}
                </div>
                <span
                  title={formatAbsoluteSecond(a.alarm_at)}
                  style={{
                    fontSize: 12,
                    color: '#999',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {formatRelative(a.alarm_at)}
                </span>
              </div>

              {/* 第 2 行：设备备注名（主标题 16px / 600） */}
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  color: remark ? '#333' : '#BBB',
                  marginBottom: 6,
                }}
              >
                {remark || '未命名'}
              </div>

              {/* 第 3 行：精确时间（秒级，独立一行） */}
              <div
                data-testid={`alarm-time-${a.id}`}
                style={{
                  fontSize: 13,
                  color: '#6B7280',
                  marginBottom: 6,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <span aria-hidden>🕐</span>
                <span>{formatAbsoluteSecond(a.alarm_at)}</span>
              </div>

              {/* 第 4 行：外呼通知（仅已通知时显示） */}
              {showNotify && phoneMask ? (
                <div
                  style={{
                    fontSize: 12,
                    color: '#43A047',
                    marginBottom: 6,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <span>✓</span>
                  <span>已外呼通知紧急联系人 {phoneMask}</span>
                </div>
              ) : null}

              {/* 虚线分隔 */}
              <div
                style={{
                  borderTop: '1px dashed #E5E7EB',
                  margin: '8px 0 6px',
                }}
              />

              {/* 第 5 行：SN（小字辅助）+ 操作按钮 */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 8,
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ fontSize: 12, color: '#9CA3AF' }}>SN：{a.device_sn}</div>
                {isPending ? (
                  <button
                    data-testid={`alarm-resolve-btn-${a.id}`}
                    onClick={() => setResolveTarget(a)}
                    style={{
                      padding: '6px 14px',
                      background: '#1F8FE6',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 14,
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    标记已处理
                  </button>
                ) : null}
              </div>
            </div>
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

      {/* 二次确认弹窗 */}
      {resolveTarget ? (
        <div
          data-testid="resolve-confirm-dialog"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1100,
          }}
          onClick={() => (resolving ? null : setResolveTarget(null))}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 22,
              width: '88%',
              maxWidth: 340,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                fontSize: 16,
                fontWeight: 600,
                marginBottom: 10,
                textAlign: 'center',
              }}
            >
              确认标记为已处理？
            </div>
            <div
              style={{
                fontSize: 13,
                color: '#666',
                marginBottom: 18,
                lineHeight: 1.6,
                textAlign: 'center',
              }}
            >
              处理后将不可撤销，请确认设备已经检查并排除风险。
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                data-testid="resolve-cancel-btn"
                onClick={() => setResolveTarget(null)}
                disabled={resolving}
                style={{
                  flex: 1,
                  padding: '10px',
                  background: '#fff',
                  color: '#666',
                  border: '1px solid #ccc',
                  borderRadius: 8,
                  cursor: resolving ? 'not-allowed' : 'pointer',
                  fontSize: 14,
                }}
              >
                取消
              </button>
              <button
                data-testid="resolve-confirm-btn"
                onClick={doResolve}
                disabled={resolving}
                style={{
                  flex: 1,
                  padding: '10px',
                  background: '#1F8FE6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  cursor: resolving ? 'not-allowed' : 'pointer',
                  fontSize: 14,
                  fontWeight: 600,
                }}
              >
                {resolving ? '处理中…' : '确认已处理'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
