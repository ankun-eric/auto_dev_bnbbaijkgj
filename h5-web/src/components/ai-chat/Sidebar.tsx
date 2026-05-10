'use client';

/**
 * [PRD-455 V7] AI 对话首页 · 左侧抽屉页全量重写
 *
 * 范围：仅 H5 端 `h5-web/src/app/(ai-chat)/ai-home/` 顶部 ☰ 触发的左侧抽屉。
 *
 * 核心规格（来自 PRD V7 最终版）：
 *  - F-01：顶栏 = 用户头像 Logo + 右侧三图标（🔔 铃铛 / ⊞ 二维码 / ⚙ 齿轮），无 × 关闭键
 *  - F-02：铃铛 ≥1 显示红点（无数字）
 *  - F-03：二维码 = 会员码入口
 *  - F-04：齿轮 = 设置入口
 *  - F-05：用户身份 = 昵称 + ID 胶囊（替代旧"VIP 会员号"），右侧复制图标
 *  - F-06：资产行四并列（积分数字 / 优惠券角标 / 订单角标 / 收藏数字）
 *  - F-07：健康档案 + 我的设备 高频入口（替代旧 4 列订单状态）
 *  - F-08：历史对话区块标题 + 右侧"管理"
 *  - F-09：4 组弱化分组（置顶 / 最近 7 天 / 最近 30 天 / 更早），空组隐藏
 *  - F-10：条目含咨询人 6 色圆点 + 角色文字 + 置顶标签
 *  - F-11：⋯ 按钮 + 左滑 同时支持，置顶 / 取消置顶 / 删除（含二次确认 + 上限 10）
 *  - F-12：管理态批量勾选，吸底 全选 / 已选 N 项 / 删除
 *  - F-13：方案 A · 通透天空 配色（#F0F9FF → #DBEAFE 整页竖向渐变）
 *  - F-14：抽屉宽度 85% / 遮罩 15%（rgba(0,0,0,0.45)）
 */

import { useState, useEffect, useMemo, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Avatar, Dialog, Toast } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import { useAuth } from '@/lib/auth';
import api from '@/lib/api';

// ─────────────────────────────────────────────────────────────────────
// 类型定义
// ─────────────────────────────────────────────────────────────────────

/** F-10 历史对话条目（含咨询人） */
interface ChatHistoryItem {
  id: string;
  title: string;
  summary?: string; // [PRD-455 F-10] 摘要文本
  time: string;
  pinned?: boolean;
  pinnedAt?: string | null; // 置顶时间（用于排序）
  /** F-10 咨询人角色：self/spouse/father/mother/child/elder/其他 */
  askerRole?: string;
}

/** F-06 资产行数据 */
interface AssetCounts {
  points: number;       // 积分余额
  couponCount: number;  // 优惠券总数
  orderCount: number;   // 订单总数
  favoriteCount: number; // 收藏总数
}

interface SidebarProps {
  visible: boolean;
  onClose: () => void;
  activeSessionId?: string | null;
  onSelectSession?: (sessionId: string) => void;
  onNewConversation?: () => void;
}

// ─────────────────────────────────────────────────────────────────────
// 常量
// ─────────────────────────────────────────────────────────────────────

/** F-13 方案 A · 通透天空 配色（严格对齐 ai-home 天蓝色板） */
const COLOR = {
  pageGradient: 'linear-gradient(180deg, #F0F9FF 0%, #DBEAFE 100%)',
  cardBg: '#FFFFFF',
  primary: '#0EA5E9',
  primaryHover: '#0284C7',
  primaryLight: '#E0F2FE',
  primaryGradient: 'linear-gradient(135deg, #38BDF8, #0284C7)',
  textPrimary: '#1F2937',
  textSecondary: '#6B7280',
  textMuted: '#9CA3AF',
  divider: '#E5E7EB',
  capsuleBg: '#F3F4F6',
  capsuleText: '#6B7280',
  danger: '#EF4444',
  pinOrange: '#F59E0B',
  pinOrangeBg: '#FED7AA',
  pinOrangeText: '#C2410C',
} as const;

/** F-10 咨询人 6 色预设（PRD §F-10） */
const ROLE_COLORS: Record<string, { color: string; label: string }> = {
  self: { color: '#0EA5E9', label: '本人' },
  spouse: { color: '#EC4899', label: '配偶' },
  father: { color: '#1E40AF', label: '爸爸' },
  mother: { color: '#E11D48', label: '妈妈' },
  child: { color: '#F59E0B', label: '孩子' },
  elder: { color: '#8B5CF6', label: '老人' },
};

/** 超出预设角色时的备用调色板（保证同角色色值固定） */
const FALLBACK_PALETTE = [
  '#10B981', '#3B82F6', '#F97316', '#06B6D4', '#A855F7', '#84CC16',
];

/** 置顶上限 */
const PIN_LIMIT = 10;

/** F-09 时间分组阈值 */
const DAY_MS = 86400000;

// ─────────────────────────────────────────────────────────────────────
// 工具函数
// ─────────────────────────────────────────────────────────────────────

function formatRelativeTime(iso: string): string {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return '';
  const diff = Date.now() - t;
  if (diff < 60 * 1000) return '刚刚';
  if (diff < 60 * 60 * 1000) return `${Math.floor(diff / 60000)}分钟前`;
  if (diff < 24 * 60 * 60 * 1000) return `${Math.floor(diff / 3600000)}小时前`;
  return new Date(iso).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}

/** F-10 角色 → 颜色映射（保证同一角色色值固定） */
function getRoleColor(askerRole?: string): { color: string; label: string } {
  if (!askerRole) return { color: COLOR.primary, label: '本人' };
  const k = askerRole.toLowerCase();
  if (ROLE_COLORS[k]) return ROLE_COLORS[k];
  // 未识别角色：基于角色名 hash 映射到调色板，保证同一角色稳定颜色
  let hash = 0;
  for (let i = 0; i < askerRole.length; i++) hash = (hash * 31 + askerRole.charCodeAt(i)) >>> 0;
  return { color: FALLBACK_PALETTE[hash % FALLBACK_PALETTE.length], label: askerRole };
}

/** F-09 4 组时间分组 */
function groupHistories(items: ChatHistoryItem[]) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const sevenDaysAgo = startOfToday - 6 * DAY_MS;
  const thirtyDaysAgo = startOfToday - 29 * DAY_MS;
  const groups: { label: string; items: ChatHistoryItem[] }[] = [
    { label: '最近 7 天', items: [] },
    { label: '最近 30 天', items: [] },
    { label: '更早', items: [] },
  ];
  items.forEach((it) => {
    const t = new Date(it.time).getTime();
    if (!Number.isFinite(t)) {
      groups[2].items.push(it);
      return;
    }
    if (t >= sevenDaysAgo) groups[0].items.push(it);
    else if (t >= thirtyDaysAgo) groups[1].items.push(it);
    else groups[2].items.push(it);
  });
  return groups.filter((g) => g.items.length > 0);
}

// ─────────────────────────────────────────────────────────────────────
// 子组件：徽标（红色实心圆 + 白色数字）
// ─────────────────────────────────────────────────────────────────────

function CountBadge({ count }: { count: number }) {
  if (!count || count <= 0) return null;
  const display = count >= 99 ? '99+' : String(count);
  return (
    <span
      style={{
        position: 'absolute',
        top: -4,
        right: -8,
        minWidth: 14,
        height: 14,
        padding: '0 3px',
        borderRadius: 7,
        background: COLOR.danger,
        color: '#fff',
        fontSize: 10,
        fontWeight: 600,
        lineHeight: '14px',
        textAlign: 'center',
        boxSizing: 'border-box',
      }}
      data-testid="bh-asset-badge"
    >
      {display}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────
// 主组件
// ─────────────────────────────────────────────────────────────────────

export default function Sidebar({
  visible,
  onClose,
  activeSessionId,
  onSelectSession,
  onNewConversation,
}: SidebarProps) {
  const router = useRouter();
  const { user } = useAuth();

  const [histories, setHistories] = useState<ChatHistoryItem[]>([]);
  const [assets, setAssets] = useState<AssetCounts>({
    points: 0,
    couponCount: 0,
    orderCount: 0,
    favoriteCount: 0,
  });
  const [unread, setUnread] = useState(0);
  const [loadFailed, setLoadFailed] = useState(false);

  // F-11 / F-12 操作态
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [swipeOpenId, setSwipeOpenId] = useState<string | null>(null);
  const [manageMode, setManageMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const swipeStartXRef = useRef<number>(0);

  // ─────────────────── 数据加载 ───────────────────
  useEffect(() => {
    if (!visible) return;
    setLoadFailed(false);

    // F-09/F-10 历史对话
    api
      .get('/api/chat-sessions')
      .then((res: any) => {
        const data = res.data || res;
        const list = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
        setHistories(
          list.map((s: any) => ({
            id: String(s.id),
            title: s.title || '新对话',
            summary: s.last_message || s.preview || s.summary || '',
            time: s.updated_at || s.created_at || '',
            pinned: !!(s.is_pinned || s.pinned),
            pinnedAt: s.pinned_at || null,
            askerRole: s.asker_role || s.role || (s.family_member_id ? 'self' : 'self'),
          }))
        );
      })
      .catch(() => setLoadFailed(true));

    // F-06 资产行数据
    api
      .get('/api/h5/user-assets')
      .then((res: any) => {
        const data = res.data || res;
        setAssets({
          points: Number(data.points) || 0,
          couponCount: Number(data.coupon_count) || 0,
          orderCount: Number(data.order_count) || 0,
          favoriteCount: Number(data.favorite_count) || 0,
        });
      })
      .catch(() => {
        // F-06 兼容旧接口：尝试 fallback 到 unread-count 拿优惠券
        api.get('/api/h5/unread-count').then((res: any) => {
          const data = res.data || res;
          setAssets((s) => ({ ...s, couponCount: Number(data.coupon_count) || 0 }));
        }).catch(() => {});
        api.get('/api/h5/order-counts').then((res: any) => {
          const data = res.data || res;
          const total = (Number(data.pending_payment) || 0) + (Number(data.pending_use) || 0);
          setAssets((s) => ({ ...s, orderCount: total }));
        }).catch(() => {});
      });

    // F-02 铃铛红点（消息未读总数 ≥1 显示）
    api
      .get('/api/v1/notifications/unread-count')
      .then((res: any) => {
        const data = res?.data ?? res;
        const cnt = data?.data?.unreadCount ?? data?.unreadCount ?? data?.unread_count ?? 0;
        setUnread(Number(cnt) || 0);
      })
      .catch(() => setUnread(0));
  }, [visible]);

  // 抽屉关闭时重置交互态
  useEffect(() => {
    if (!visible) {
      setMenuOpenId(null);
      setSwipeOpenId(null);
      setManageMode(false);
      setSelectedIds(new Set());
    }
  }, [visible]);

  // ─────────────────── 计算分组（F-09） ───────────────────
  const { pinnedItems, groups } = useMemo(() => {
    const pinned = histories
      .filter((h) => h.pinned)
      .sort((a, b) => {
        const ta = new Date(a.pinnedAt || a.time).getTime();
        const tb = new Date(b.pinnedAt || b.time).getTime();
        return tb - ta;
      })
      .slice(0, PIN_LIMIT);
    const unpinned = histories.filter((h) => !h.pinned);
    return { pinnedItems: pinned, groups: groupHistories(unpinned) };
  }, [histories]);

  // ─────────────────── 导航 ───────────────────
  const navigateTo = (path: string) => {
    onClose();
    router.push(path);
  };

  // ─────────────────── F-05 复制 ID ───────────────────
  const handleCopyId = (id: string) => {
    if (!id) return;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(id)
        .then(() => Toast.show({ content: 'ID 已复制', icon: 'success' }))
        .catch(() => Toast.show({ content: '复制失败' }));
    } else {
      // 浏览器兼容兜底
      try {
        const ta = document.createElement('textarea');
        ta.value = id;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        Toast.show({ content: 'ID 已复制', icon: 'success' });
      } catch {
        Toast.show({ content: '复制失败' });
      }
    }
  };

  // ─────────────────── F-11 单条操作 ───────────────────
  const handleSelectSession = (id: string) => {
    if (manageMode) {
      // F-12 管理态点击 = 切换勾选
      setSelectedIds((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id); else next.add(id);
        return next;
      });
      return;
    }
    if (menuOpenId || swipeOpenId) {
      setMenuOpenId(null);
      setSwipeOpenId(null);
      return;
    }
    if (onSelectSession) onSelectSession(id);
    else navigateTo(`/chat/${id}`);
  };

  const togglePin = async (id: string) => {
    setMenuOpenId(null);
    setSwipeOpenId(null);
    const item = histories.find((h) => h.id === id);
    if (!item) return;
    // F-11 上限提示
    if (!item.pinned && pinnedItems.length >= PIN_LIMIT) {
      Toast.show({ content: `最多置顶 ${PIN_LIMIT} 条对话` });
      return;
    }
    const willPin = !item.pinned;
    // 乐观更新
    setHistories((prev) =>
      prev.map((h) =>
        h.id === id ? { ...h, pinned: willPin, pinnedAt: willPin ? new Date().toISOString() : null } : h
      )
    );
    try {
      await api.post('/api/chat/history/pin', { id, isPinned: willPin });
      Toast.show({ content: willPin ? '已置顶' : '已取消置顶' });
    } catch {
      // 接口失败不回滚（保持乐观），仅静默
    }
  };

  const deleteOne = async (id: string) => {
    setMenuOpenId(null);
    setSwipeOpenId(null);
    const ok = await Dialog.confirm({
      content: '确认删除该对话？',
      confirmText: '确认',
      cancelText: '取消',
    });
    if (!ok) return;
    setHistories((prev) => prev.filter((h) => h.id !== id));
    try {
      await api.post('/api/chat/history/delete', { ids: [id] });
      Toast.show({ content: '已删除', icon: 'success' });
    } catch {
      Toast.show({ content: '删除可能未同步，请稍后刷新' });
    }
  };

  // ─────────────────── F-12 批量删除 ───────────────────
  const batchDelete = async () => {
    if (selectedIds.size === 0) return;
    const n = selectedIds.size;
    const ok = await Dialog.confirm({
      content: `确认删除已选 ${n} 条对话？`,
      confirmText: '确认',
      cancelText: '取消',
    });
    if (!ok) return;
    const ids = Array.from(selectedIds);
    setHistories((prev) => prev.filter((h) => !selectedIds.has(h.id)));
    setSelectedIds(new Set());
    setManageMode(false);
    try {
      await api.post('/api/chat/history/delete', { ids });
      Toast.show({ content: '已删除', icon: 'success' });
    } catch {
      Toast.show({ content: '删除可能未同步，请稍后刷新' });
    }
  };

  const allItems = useMemo(
    () => [...pinnedItems, ...groups.flatMap((g) => g.items)],
    [pinnedItems, groups]
  );

  const toggleSelectAll = () => {
    if (selectedIds.size === allItems.length && allItems.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(allItems.map((it) => it.id)));
    }
  };

  // ─────────────────── F-11 左滑手势 ───────────────────
  const handleTouchStart = (e: React.TouchEvent, id: string) => {
    if (manageMode) return;
    swipeStartXRef.current = e.touches[0].clientX;
  };
  const handleTouchEnd = (e: React.TouchEvent, id: string) => {
    if (manageMode) return;
    const dx = swipeStartXRef.current - e.changedTouches[0].clientX;
    if (dx > 50) {
      setSwipeOpenId(id);
      setMenuOpenId(null);
    } else if (dx < -50 && swipeOpenId === id) {
      setSwipeOpenId(null);
    }
  };

  // ─────────────────── 渲染辅助 ───────────────────

  /** F-10 咨询人圆点 + 文字 */
  const renderRoleDot = (role?: string) => {
    const { color, label } = getRoleColor(role);
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, color: COLOR.textSecondary }}>
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: color,
            display: 'inline-block',
            flexShrink: 0,
          }}
        />
        <span>{label}</span>
      </span>
    );
  };

  /** F-10 单条历史对话 */
  const renderHistoryItem = (item: ChatHistoryItem, fromPinned = false) => {
    const isActive = activeSessionId === item.id;
    const menuVisible = menuOpenId === item.id;
    const swipeVisible = swipeOpenId === item.id;
    const checked = selectedIds.has(item.id);

    return (
      <div
        key={item.id}
        data-testid="bh-history-item"
        style={{
          position: 'relative',
          marginBottom: 4,
          borderRadius: 10,
          overflow: 'hidden',
        }}
      >
        {/* 左滑暴露的右侧两色块按钮（F-11） */}
        {swipeVisible && !manageMode && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              right: 0,
              bottom: 0,
              display: 'flex',
              gap: 0,
              zIndex: 1,
            }}
          >
            <button
              onClick={(e) => {
                e.stopPropagation();
                togglePin(item.id);
              }}
              style={{
                background: COLOR.pinOrange,
                color: '#fff',
                border: 'none',
                padding: '0 14px',
                fontSize: 13,
                cursor: 'pointer',
                height: '100%',
              }}
              data-testid="bh-swipe-pin"
            >
              {item.pinned ? '取消置顶' : '置顶'}
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                deleteOne(item.id);
              }}
              style={{
                background: COLOR.danger,
                color: '#fff',
                border: 'none',
                padding: '0 14px',
                fontSize: 13,
                cursor: 'pointer',
                height: '100%',
              }}
              data-testid="bh-swipe-delete"
            >
              删除
            </button>
          </div>
        )}

        <div
          onClick={() => handleSelectSession(item.id)}
          onTouchStart={(e) => handleTouchStart(e, item.id)}
          onTouchEnd={(e) => handleTouchEnd(e, item.id)}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            padding: '10px 12px',
            background: isActive ? COLOR.primaryLight : COLOR.cardBg,
            cursor: 'pointer',
            transform: swipeVisible ? 'translateX(-160px)' : 'translateX(0)',
            transition: 'transform 0.2s ease-out',
            position: 'relative',
            zIndex: 2,
          }}
          data-active={isActive ? 'true' : 'false'}
        >
          {/* F-12 管理态勾选框 */}
          {manageMode && (
            <div
              style={{
                width: 20,
                height: 20,
                borderRadius: '50%',
                border: `1.5px solid ${checked ? COLOR.primary : COLOR.divider}`,
                background: checked ? COLOR.primary : 'transparent',
                color: '#fff',
                fontSize: 14,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                marginTop: 2,
              }}
              data-testid="bh-history-checkbox"
            >
              {checked ? '✓' : ''}
            </div>
          )}

          {/* 主体 */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span
                style={{
                  fontSize: 14,
                  color: COLOR.textPrimary,
                  fontWeight: 500,
                  flex: 1,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {item.title}
              </span>
              {item.pinned && (
                <span
                  style={{
                    fontSize: 10,
                    color: COLOR.pinOrangeText,
                    background: COLOR.pinOrangeBg,
                    padding: '1px 6px',
                    borderRadius: 4,
                    flexShrink: 0,
                  }}
                  data-testid="bh-pin-tag"
                >
                  置顶
                </span>
              )}
            </div>
            {item.summary && (
              <div
                style={{
                  fontSize: 12,
                  color: COLOR.textSecondary,
                  marginTop: 2,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {item.summary}
              </div>
            )}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginTop: 4,
              }}
            >
              {renderRoleDot(item.askerRole)}
              <span style={{ fontSize: 11, color: COLOR.textMuted }}>{formatRelativeTime(item.time)}</span>
            </div>
          </div>

          {/* F-11 ⋯ 按钮（管理态下隐藏） */}
          {!manageMode && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSwipeOpenId(null);
                setMenuOpenId(menuOpenId === item.id ? null : item.id);
              }}
              style={{
                background: 'transparent',
                border: 'none',
                color: COLOR.textMuted,
                fontSize: 18,
                lineHeight: 1,
                cursor: 'pointer',
                padding: '4px 6px',
                flexShrink: 0,
                alignSelf: 'flex-start',
              }}
              aria-label="更多"
              data-testid="bh-history-more-btn"
            >
              ⋯
            </button>
          )}
        </div>

        {/* F-11 ⋯ 弹出菜单 */}
        {menuVisible && !manageMode && (
          <div
            style={{
              position: 'absolute',
              top: 36,
              right: 8,
              background: COLOR.cardBg,
              borderRadius: 8,
              boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
              zIndex: 10,
              minWidth: 110,
              overflow: 'hidden',
              border: `1px solid ${COLOR.divider}`,
            }}
            data-testid="bh-history-menu"
          >
            <button
              onClick={(e) => {
                e.stopPropagation();
                togglePin(item.id);
              }}
              style={{
                display: 'block',
                width: '100%',
                padding: '10px 14px',
                background: 'transparent',
                border: 'none',
                fontSize: 13,
                color: COLOR.textPrimary,
                textAlign: 'left',
                cursor: 'pointer',
              }}
            >
              {item.pinned ? '取消置顶' : '置顶'}
            </button>
            <div style={{ height: 1, background: COLOR.divider }} />
            <button
              onClick={(e) => {
                e.stopPropagation();
                deleteOne(item.id);
              }}
              style={{
                display: 'block',
                width: '100%',
                padding: '10px 14px',
                background: 'transparent',
                border: 'none',
                fontSize: 13,
                color: COLOR.danger,
                textAlign: 'left',
                cursor: 'pointer',
              }}
            >
              删除
            </button>
          </div>
        )}
      </div>
    );
  };

  // ─────────────────── 渲染 ───────────────────
  if (!visible) return null;

  const userId = (user as any)?.user_no || (user as any)?.id || '';
  const idDisplay = userId ? String(userId) : '--';
  const empty = allItems.length === 0;

  return (
    <>
      <div
        className="fixed inset-0 z-[200] flex"
        data-testid="bh-sidebar-root"
        onClick={() => {
          // 点击遮罩关闭抽屉（F-14）
          setMenuOpenId(null);
          setSwipeOpenId(null);
          onClose();
        }}
      >
        {/* 抽屉主体（85%）—— F-14 */}
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            width: '85%',
            height: '100%',
            background: COLOR.pageGradient,
            display: 'flex',
            flexDirection: 'column',
            animation: 'bh-slide-in-left 0.25s ease-out',
            position: 'relative',
            zIndex: 1,
          }}
          data-testid="bh-sidebar-panel"
        >
          {/* ─── F-01 顶栏：头像 + 三图标（无 × 关闭键） ─── */}
          <div
            style={{
              padding: '12px 16px 8px 16px',
              paddingTop: 'max(12px, calc(env(safe-area-inset-top) + 8px))',
              flexShrink: 0,
            }}
            data-testid="bh-sidebar-top"
          >
            <div style={{ display: 'flex', alignItems: 'center' }}>
              {/* 左：用户头像 Logo（48×48） */}
              <Avatar
                src={user?.avatar || ''}
                style={{
                  '--size': '48px',
                  '--border-radius': '50%',
                  background: COLOR.primary,
                  color: '#fff',
                  fontSize: 20,
                  flexShrink: 0,
                } as any}
              />

              {/* 右：三图标整体右对齐，垂直居中对齐头像 */}
              <div
                style={{
                  marginLeft: 'auto',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 16,
                }}
              >
                {/* F-02 铃铛（仅红点） */}
                <button
                  onClick={() => navigateTo('/notifications')}
                  style={{
                    position: 'relative',
                    width: 24,
                    height: 24,
                    background: 'transparent',
                    border: 'none',
                    padding: 0,
                    cursor: 'pointer',
                    color: COLOR.textPrimary,
                    fontSize: 22,
                    lineHeight: 1,
                  }}
                  aria-label="消息"
                  data-testid="bh-icon-bell"
                >
                  🔔
                  {unread > 0 && (
                    <span
                      style={{
                        position: 'absolute',
                        top: 2,
                        right: 2,
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: COLOR.danger,
                      }}
                      data-testid="bh-icon-bell-dot"
                    />
                  )}
                </button>
                {/* F-03 二维码（会员码） */}
                <button
                  onClick={() => navigateTo('/member-qrcode')}
                  style={{
                    width: 24,
                    height: 24,
                    background: 'transparent',
                    border: 'none',
                    padding: 0,
                    cursor: 'pointer',
                    color: COLOR.textPrimary,
                    fontSize: 22,
                    lineHeight: 1,
                  }}
                  aria-label="会员码"
                  data-testid="bh-icon-qrcode"
                >
                  ⊞
                </button>
                {/* F-04 齿轮（设置） */}
                <button
                  onClick={() => navigateTo('/ai-settings')}
                  style={{
                    width: 24,
                    height: 24,
                    background: 'transparent',
                    border: 'none',
                    padding: 0,
                    cursor: 'pointer',
                    color: COLOR.textPrimary,
                    fontSize: 22,
                    lineHeight: 1,
                  }}
                  aria-label="设置"
                  data-testid="bh-icon-settings"
                >
                  ⚙
                </button>
              </div>
            </div>

            {/* F-05 用户身份信息：昵称 + ID 胶囊 */}
            <div style={{ marginTop: 10 }}>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 700,
                  color: COLOR.textPrimary,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
                data-testid="bh-user-nickname"
              >
                {user?.nickname || '未登录'}
              </div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  marginTop: 6,
                  padding: '4px 10px',
                  background: COLOR.capsuleBg,
                  borderRadius: 10,
                  fontSize: 12,
                  color: COLOR.capsuleText,
                  cursor: 'pointer',
                }}
                onClick={() => handleCopyId(idDisplay)}
                data-testid="bh-id-capsule"
              >
                <span>ID: {idDisplay}</span>
                <span
                  style={{ fontSize: 14, lineHeight: 1, display: 'inline-flex' }}
                  aria-label="复制 ID"
                >
                  📋
                </span>
              </div>
            </div>
          </div>

          {/* 内容区：仅历史对话可滚动；顶部用户卡片 + 资产 + 高频入口固定（F-14） */}
          <div
            style={{
              padding: '0 16px',
              flexShrink: 0,
            }}
          >
            {/* ─── F-06 资产行四并列 ─── */}
            <div
              style={{
                background: COLOR.cardBg,
                borderRadius: 12,
                padding: '12px 8px',
                display: 'flex',
                marginTop: 8,
              }}
              data-testid="bh-asset-row"
            >
              {/* 1. 积分 */}
              <div
                style={{ flex: 1, textAlign: 'center', cursor: 'pointer' }}
                onClick={() => navigateTo('/points-center')}
                data-testid="bh-asset-points"
              >
                <div style={{ fontSize: 16, fontWeight: 700, color: COLOR.textPrimary, lineHeight: 1.2 }}>
                  {assets.points}
                </div>
                <div style={{ fontSize: 12, color: COLOR.textSecondary, marginTop: 4 }}>积分</div>
              </div>
              {/* 2. 优惠券（图标 + 角标） */}
              <div
                style={{ flex: 1, textAlign: 'center', cursor: 'pointer' }}
                onClick={() => navigateTo('/my-coupons')}
                data-testid="bh-asset-coupons"
              >
                <div style={{ position: 'relative', display: 'inline-block', fontSize: 22, lineHeight: '24px' }}>
                  🎫
                  <CountBadge count={assets.couponCount} />
                </div>
                <div style={{ fontSize: 12, color: COLOR.textSecondary, marginTop: 4 }}>优惠券</div>
              </div>
              {/* 3. 订单（图标 + 角标） */}
              <div
                style={{ flex: 1, textAlign: 'center', cursor: 'pointer' }}
                onClick={() => navigateTo('/unified-orders')}
                data-testid="bh-asset-orders"
              >
                <div style={{ position: 'relative', display: 'inline-block', fontSize: 22, lineHeight: '24px' }}>
                  📦
                  <CountBadge count={assets.orderCount} />
                </div>
                <div style={{ fontSize: 12, color: COLOR.textSecondary, marginTop: 4 }}>订单</div>
              </div>
              {/* 4. 收藏（数字） */}
              <div
                style={{ flex: 1, textAlign: 'center', cursor: 'pointer' }}
                onClick={() => navigateTo('/my-favorites')}
                data-testid="bh-asset-favorites"
              >
                <div style={{ fontSize: 16, fontWeight: 700, color: COLOR.textPrimary, lineHeight: 1.2 }}>
                  {assets.favoriteCount}
                </div>
                <div style={{ fontSize: 12, color: COLOR.textSecondary, marginTop: 4 }}>收藏</div>
              </div>
            </div>

            {/* ─── F-07 健康档案 + 我的设备 高频入口 ─── */}
            <div style={{ display: 'flex', gap: 12, marginTop: 12 }} data-testid="bh-quick-entry-row">
              <button
                onClick={() => navigateTo('/health-archive')}
                style={{
                  flex: 1,
                  background: COLOR.cardBg,
                  borderRadius: 12,
                  border: 'none',
                  padding: '12px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
                data-testid="bh-entry-health-archive"
              >
                <span style={{ fontSize: 24, lineHeight: 1, flexShrink: 0 }}>🏥</span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span
                    style={{
                      display: 'block',
                      fontSize: 14,
                      fontWeight: 600,
                      color: COLOR.textPrimary,
                      lineHeight: 1.2,
                    }}
                  >
                    健康档案
                  </span>
                  <span style={{ display: 'block', fontSize: 12, color: COLOR.textSecondary, marginTop: 2 }}>
                    家人健康管理
                  </span>
                </span>
              </button>
              <button
                onClick={() => navigateTo('/my-devices')}
                style={{
                  flex: 1,
                  background: COLOR.cardBg,
                  borderRadius: 12,
                  border: 'none',
                  padding: '12px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
                data-testid="bh-entry-devices"
              >
                <span style={{ fontSize: 24, lineHeight: 1, flexShrink: 0 }}>📱</span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span
                    style={{
                      display: 'block',
                      fontSize: 14,
                      fontWeight: 600,
                      color: COLOR.textPrimary,
                      lineHeight: 1.2,
                    }}
                  >
                    我的设备
                  </span>
                  <span style={{ display: 'block', fontSize: 12, color: COLOR.textSecondary, marginTop: 2 }}>
                    硬件设备管理
                  </span>
                </span>
              </button>
            </div>

            {/* ─── F-08 历史对话区块标题 ─── */}
            <div
              style={{
                marginTop: 16,
                marginBottom: 6,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
              data-testid="bh-history-section-header"
            >
              <span style={{ fontSize: 14, fontWeight: 700, color: COLOR.textPrimary }}>历史对话</span>
              {!manageMode ? (
                <button
                  onClick={() => {
                    setMenuOpenId(null);
                    setSwipeOpenId(null);
                    setManageMode(true);
                  }}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: COLOR.primary,
                    fontSize: 13,
                    cursor: 'pointer',
                    padding: '2px 6px',
                  }}
                  data-testid="bh-history-manage-btn"
                  disabled={empty}
                >
                  管理
                </button>
              ) : (
                <button
                  onClick={() => {
                    setManageMode(false);
                    setSelectedIds(new Set());
                  }}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: COLOR.primary,
                    fontSize: 13,
                    cursor: 'pointer',
                    padding: '2px 6px',
                  }}
                  data-testid="bh-history-done-btn"
                >
                  完成
                </button>
              )}
            </div>
          </div>

          {/* ─── F-09 / F-10 历史对话列表（仅此区域可滚动） ─── */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '0 16px',
              paddingBottom: manageMode ? 64 : 16,
              minHeight: 0,
            }}
            data-testid="bh-history-scroll"
          >
            {/* 置顶分组 */}
            {pinnedItems.length > 0 && (
              <div style={{ marginBottom: 8 }} data-testid="bh-history-group-pinned">
                <div
                  style={{
                    fontSize: 11,
                    color: COLOR.textMuted,
                    margin: '6px 0 4px 0',
                    paddingLeft: 2,
                  }}
                >
                  置顶
                </div>
                {pinnedItems.map((it) => renderHistoryItem(it, true))}
              </div>
            )}

            {/* 时间分组 */}
            {groups.map((g) => (
              <div key={g.label} style={{ marginBottom: 8 }} data-testid={`bh-history-group-${g.label}`}>
                <div
                  style={{
                    fontSize: 11,
                    color: COLOR.textMuted,
                    margin: '6px 0 4px 0',
                    paddingLeft: 2,
                  }}
                >
                  {g.label}
                </div>
                {g.items.map((it) => renderHistoryItem(it, false))}
              </div>
            ))}

            {/* 空态 */}
            {empty && !loadFailed && (
              <div
                style={{
                  textAlign: 'center',
                  padding: '40px 16px',
                }}
                data-testid="bh-history-empty"
              >
                <div style={{ fontSize: 36, marginBottom: 8 }}>💬</div>
                <div style={{ fontSize: 13, color: COLOR.textSecondary, marginBottom: 16 }}>
                  还没有对话记录，开始你的第一次咨询吧
                </div>
                <button
                  onClick={() => {
                    if (onNewConversation) onNewConversation();
                    onClose();
                  }}
                  style={{
                    background: COLOR.primary,
                    color: '#fff',
                    border: 'none',
                    borderRadius: 16,
                    padding: '6px 18px',
                    fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  返回首页
                </button>
              </div>
            )}

            {/* 异常态 */}
            {loadFailed && (
              <div
                style={{
                  textAlign: 'center',
                  padding: '40px 16px',
                  fontSize: 13,
                  color: COLOR.textSecondary,
                }}
                data-testid="bh-history-error"
              >
                <div>加载失败，</div>
                <button
                  onClick={() => {
                    setLoadFailed(false);
                    // 重新触发加载
                    setHistories([]);
                    api.get('/api/chat-sessions').then((res: any) => {
                      const data = res.data || res;
                      const list = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
                      setHistories(
                        list.map((s: any) => ({
                          id: String(s.id),
                          title: s.title || '新对话',
                          summary: s.last_message || s.preview || '',
                          time: s.updated_at || s.created_at || '',
                          pinned: !!(s.is_pinned || s.pinned),
                          pinnedAt: s.pinned_at || null,
                          askerRole: s.asker_role || 'self',
                        }))
                      );
                    }).catch(() => setLoadFailed(true));
                  }}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: COLOR.primary,
                    cursor: 'pointer',
                    fontSize: 13,
                  }}
                >
                  点击重试
                </button>
              </div>
            )}
          </div>

          {/* ─── F-12 管理态底部操作条 ─── */}
          {manageMode && (
            <div
              style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                background: COLOR.cardBg,
                borderTop: `1px solid ${COLOR.divider}`,
                padding: '12px 16px',
                paddingBottom: 'calc(12px + env(safe-area-inset-bottom))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                zIndex: 5,
              }}
              data-testid="bh-manage-bar"
            >
              <button
                onClick={toggleSelectAll}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: COLOR.textPrimary,
                  fontSize: 14,
                  cursor: 'pointer',
                  padding: '4px 0',
                }}
                data-testid="bh-manage-select-all"
              >
                全选
              </button>
              <span
                style={{ fontSize: 13, color: COLOR.textSecondary }}
                data-testid="bh-manage-count"
              >
                已选 {selectedIds.size} 项
              </span>
              <button
                onClick={batchDelete}
                disabled={selectedIds.size === 0}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: selectedIds.size === 0 ? COLOR.textMuted : COLOR.danger,
                  fontSize: 14,
                  cursor: selectedIds.size === 0 ? 'not-allowed' : 'pointer',
                  padding: '4px 0',
                  fontWeight: 500,
                }}
                data-testid="bh-manage-delete"
              >
                删除
              </button>
            </div>
          )}
        </div>

        {/* 右侧 15% 遮罩（F-14） */}
        <div
          style={{
            flex: 1,
            background: 'rgba(0, 0, 0, 0.45)',
          }}
          data-testid="bh-sidebar-mask"
        />
      </div>

      <style jsx global>{`
        @keyframes bh-slide-in-left {
          from { transform: translateX(-100%); }
          to { transform: translateX(0); }
        }
      `}</style>
    </>
  );
}
