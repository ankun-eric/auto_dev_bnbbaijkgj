'use client';

/**
 * [PRD-455 V7] AI 对话首页 · 左侧抽屉页全量重写
 *
 * 范围：仅 H5 端 `h5-web/src/app/(ai-chat)/ai-home/` 顶部 ☰ 触发的左侧抽屉。
 *
 * 核心规格（来自 PRD V7 最终版）：
 *  - F-01：顶栏 = 用户头像 Logo + 右侧两图标（🔔 铃铛 / ⚙ 齿轮）—— [BUG-457] 删除中间「⊞ 会员二维码」
 *  - F-02：铃铛 ≥1 显示红点（无数字）
 *  - F-03：二维码 = 会员码入口   —— [BUG-457] 已废弃
 *  - F-04：齿轮 = 设置入口
 *  - F-05：用户身份 = 昵称 + ID 胶囊  —— [BUG-457] 删除右侧 📋；点击胶囊跳 /profile/edit
 *  - F-06：资产行四并列（积分数字 / 优惠券角标 / 订单角标 / 收藏数字）
 *           —— [BUG-457] 接入「我的」同款接口（points/coupons/orders/users me-stats）
 *  - F-07：健康档案 + 我的设备 高频入口（替代旧 4 列订单状态）
 *  - F-08：历史对话区块标题 + 右侧"管理"
 *  - F-09：4 组弱化分组（置顶 / 最近 7 天 / 最近 30 天 / 更早），空组隐藏
 *  - F-10：条目含咨询人 6 色圆点 + 角色文字 + 置顶标签
 *  - F-11：⋯ 按钮 + 左滑 同时支持，置顶 / 取消置顶 / 删除（含二次确认 + 上限 10）
 *  - F-12：管理态批量勾选，吸底 全选 / 已选 N 项 / 删除
 *  - F-13：方案 A · 通透天空 配色（#F0F9FF → #DBEAFE 整页竖向渐变）
 *  - F-14：抽屉宽度 85% / 遮罩 15%（rgba(0,0,0,0.45)）
 *
 * [BUG-457 (2026-05-11)] 抽屉页优化 4 个 Bug：
 *  1. 删除 ID 胶囊右侧 📋 复制图标，点击胶囊改为跳转个人资料编辑页
 *  2. 删除顶部「⊞ 会员二维码」入口
 *  3. 资产 4 格接入正确接口（积分/优惠券/订单/收藏），避免全 0
 *  4. 历史对话 .catch 收窄（注：此项已被 INCIDENT-20260513-03 修订为「全量异常优雅降级为空列表」）
 *
 * [BUG-458 (2026-05-11)] 顶栏左上角「账号信息与头像未同行」修复：
 *  - 顶栏由「头像+图标 / 昵称 / ID 胶囊」三行纵向堆叠，重构为单行水平 Flex：
 *      头像（固定宽）│ 名片块（弹性宽，内部纵向：昵称+ID 胶囊）│ 顶栏图标组（固定宽，右对齐）
 *  - 名片块设 `flex:1; min-width:0;` + 昵称 `text-overflow:ellipsis` 单行省略号兜底
 *  - 取消 ID 胶囊点击复制行为：仅纯展示，不响应点击、不显示复制图标、不显示 Toast、不带 cursor:pointer
 *
 * [INCIDENT-20260513-03 (2026-05-13) P0] 抽屉「历史会话」加载失败修复：
 *  - 现象：全量账号在抽屉「历史会话」区域显示「加载失败，点击重试」，重试无效。
 *  - 根因：BUG-457 引入的 try/catch 把任何异常（含字段缺失/瞬时 5xx/网络抖动）
 *    一律 setLoadFailed(true) 触发红色错误态，与产品兜底预期不符。
 *  - 修复（PRD 4.4 第 4 档「优雅降级」）：
 *      1. loadHistories 全量异常一律视为空列表，进入「暂无历史对话」空态；
 *      2. 解析阶段做更强的类型兜底（支持 [] / {items: []} / {data: []}）；
 *      3. console.warn 记录原始 error 便于线上排查；
 *      4. 保留接口 200 正常返回的全部映射逻辑。
 *  - 保留：BUG-460/461/462/PRD-463 所有关键修复完全不动。
 *
 * [BUG-461 (2026-05-11)] 抽屉「历史对话」三 Bug 联合修复：
 *  - Bug A：⋯ 弹出菜单改用 `ReactDOM.createPortal` 渲染到 `document.body`，并基于
 *    `getBoundingClientRect()` 动态计算位置，菜单 `z-index = 9999` 高于抽屉遮罩；
 *    新增「点击菜单外区域自动关闭」全局监听；菜单距底部不足时向上翻转避让屏幕边缘。
 *  - Bug B：`ChatHistoryItem` 新增 `family_member_id / nickname` 字段；
 *    `askerRole` 来源升级为后端新返回的 `family_member_relation`（self/spouse/...）。
 *  - Bug C 配套：监听 `bh-history-refresh` 自定义事件后，主动重新拉取历史列表，
 *    供「咨询人切换 → 立即创建新会话」流程消费。
 */

import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { useRouter } from 'next/navigation';
import { Avatar, Dialog, Toast } from 'antd-mobile';
// [AI对话模式优化 PRD v1.0 §7] 全局 Toast 规范封装（位置上方 1/3 + 类型差异化配色）
import { ToastUnified } from '@/lib/toast-unified';
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
  /** [BUG-461] 咨询人家庭成员 ID（本人=null） */
  familyMemberId?: number | null;
  /** [BUG-461] 咨询人昵称（用于 hover 提示或长文展示） */
  familyMemberNickname?: string | null;
}

/** F-06 资产行数据 */
interface AssetCounts {
  points: number;       // 积分余额
  couponCount: number;  // 优惠券总数
  orderCount: number;   // 订单总数（v2_pending_receipt + v2_pending_use）
  favoriteCount: number; // 收藏总数
  // [PRD-463 2026-05-11] 智能定位 Tab 所需的拆分字段
  // - v2_pending_receipt：抽屉口径下「待收货 Tab」聚合数（pending_shipment + pending_receipt）
  // - v2_pending_use：抽屉口径下「待使用 Tab」聚合数（pending_appointment + appointed + pending_use + partial_used）
  v2Receipt: number;
  v2Use: number;
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

/**
 * [PRD-463 2026-05-11] 资产格角标数字展示规则（边界值）：
 *   0     → '0'（不隐藏，保持四格一致）
 *   1~9   → 显示真实数字
 *   ≥10   → 显示 '9+'
 * 适用于「优惠券 / 收藏 / 订单」三格；
 * 积分通常为较大数值，保留原始数字不应用本截断。
 */
const formatBadge = (n: number): string => {
  const v = Number.isFinite(n) ? Number(n) : 0;
  if (v <= 0) return '0';
  return v >= 10 ? '9+' : String(v);
};

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
// 主组件
// ─────────────────────────────────────────────────────────────────────
// [PRD-463 2026-05-11] CountBadge 子组件已废弃：
// 资产行改为「大号数字 + 下方文字」统一风格，不再使用图标右上角小红点徽标。
// 数字展示规则由 formatBadge 工具函数承担。

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
    v2Receipt: 0,
    v2Use: 0,
  });
  const [unread, setUnread] = useState(0);
  const [loadFailed, setLoadFailed] = useState(false);

  // F-11 / F-12 操作态
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [swipeOpenId, setSwipeOpenId] = useState<string | null>(null);
  const [manageMode, setManageMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const swipeStartXRef = useRef<number>(0);

  // [BUG-461 Fix-A] ⋯ 菜单 Portal 化所需的"菜单几何位置"
  // - anchorRect：触发按钮的 DOM 矩形（用于计算菜单出现位置）
  // - 菜单本身渲染到 document.body 的最外层，z-index = 9999，
  //   不再受抽屉容器/卡片 overflow:hidden 与堆叠上下文限制。
  const [menuAnchorRect, setMenuAnchorRect] = useState<DOMRect | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  // ─────────────────── 数据加载 ───────────────────
  // 历史对话加载封装（供 useEffect 与「重试」按钮共用）
  //
  // [INCIDENT-20260513-03 (2026-05-13) P0 修复] 历史会话加载失败兜底：
  //   线上反馈：H5 端抽屉「历史会话」列表全量账号显示「加载失败，点击重试」，
  //   数据库实际有数据，根因是 BUG-457 引入的 try/catch 把任何异常（包括
  //   响应字段缺失、瞬时 5xx、网络抖动等）一律视为致命错误并显示红色错误态。
  //
  //   修复策略（PRD 4.4 第 4 档兜底——前端始终优雅降级）：
  //     - 接口成功 → 正常映射列表
  //     - 接口异常（任意类型）→ 视为空数据，进入「暂无历史对话」空态，
  //       不再显示红色「加载失败」按钮；同时 console.warn 记录便于排查
  //     - 解析阶段做更强的类型兜底，避免 res / data 为意外形态时抛错
  //
  //   这样保证用户在任何接口异常情况下都能继续使用 AI 对话功能，
  //   不会因为历史列表问题被红色报错挡住流程。
  const loadHistories = useCallback(async () => {
    setLoadFailed(false);
    try {
      const res: any = await api.get('/api/chat-sessions');
      const data = res?.data ?? res;
      // 强化兜底：支持 [] / { items: [] } / { data: [] } 多种返回结构
      const rawList = Array.isArray(data)
        ? data
        : Array.isArray((data as any)?.items)
          ? (data as any).items
          : Array.isArray((data as any)?.data)
            ? (data as any).data
            : [];
      const mapped = rawList
        .filter((s: any) => s && (s.id !== undefined && s.id !== null))
        .map((s: any) => ({
          id: String(s.id),
          title: s.title || '新对话',
          summary: s.last_message || s.preview || s.summary || '',
          time: s.updated_at || s.created_at || '',
          pinned: !!(s.is_pinned || s.pinned),
          pinnedAt: s.pinned_at || null,
          // [BUG-461 Fix-B] 咨询人角色优先消费后端新返回的 family_member_relation 字段，
          // 兜底兼容历史字段 asker_role / role，仍然没有则视为本人
          askerRole:
            s.family_member_relation ||
            s.familyMemberRelation ||
            s.asker_role ||
            s.role ||
            'self',
          familyMemberId:
            s.family_member_id !== undefined
              ? s.family_member_id
              : s.familyMemberId ?? null,
          familyMemberNickname:
            s.family_member_nickname ?? s.familyMemberNickname ?? null,
        }));
      setHistories(mapped);
    } catch (err) {
      // [INCIDENT-20260513-03] 全量异常都优雅降级为空列表，不再触发红色错误态
      if (typeof console !== 'undefined' && console.warn) {
        console.warn('[Sidebar] loadHistories soft-fail, fallback to empty:', err);
      }
      setHistories([]);
      // 注意：刻意不 setLoadFailed(true)，避免再次出现 P0「加载失败」红屏
    }
  }, []);

  useEffect(() => {
    if (!visible) return;

    // [BUG-457 Fix-4] 历史对话：F-09 / F-10
    loadHistories();

    // [BUG-457 Fix-3] 资产 4 格：完全替换为「我的」页面同款接口
    // - 积分： GET /api/points/summary -> available_points
    // - 优惠券：GET /api/coupons/summary -> available_count
    // - 订单： GET /api/orders/unified/counts -> v2_pending_receipt + v2_pending_use
    //          [PRD-463 2026-05-11] 切换到 v2_* 字段，与订单列表「待收货 / 待使用 Tab」口径一致
    //          严禁使用旧字段 pending_receipt / pending_use（它们仅含单一状态，会漏算
    //          pending_shipment / pending_appointment / appointed / partial_used 等）
    // - 收藏： GET /api/users/me/stats -> favorite_count
    // 任意接口失败仅影响该单格（保持 0），不互相牵连
    api
      .get('/api/points/summary')
      .then((res: any) => {
        const data = res?.data ?? res;
        const v = Number(data?.available_points ?? data?.total_points ?? 0) || 0;
        setAssets((s) => ({ ...s, points: v }));
      })
      .catch(() => {});

    api
      .get('/api/coupons/summary')
      .then((res: any) => {
        const data = res?.data ?? res;
        const v = Number(data?.available_count ?? data?.available ?? 0) || 0;
        setAssets((s) => ({ ...s, couponCount: v }));
      })
      .catch(() => {});

    api
      .get('/api/orders/unified/counts')
      .then((res: any) => {
        const data = res?.data ?? res;
        // [PRD-463 2026-05-11] 切换至 v2_* 字段，确保抽屉订单数字 ≡ 订单列表「待收货 + 待使用 Tab」之和
        const v2Receipt = Number(data?.v2_pending_receipt) || 0;
        const v2Use = Number(data?.v2_pending_use) || 0;
        const total = v2Receipt + v2Use;
        setAssets((s) => ({ ...s, orderCount: total, v2Receipt, v2Use }));
      })
      .catch(() => {});

    api
      .get('/api/users/me/stats')
      .then((res: any) => {
        const data = res?.data ?? res;
        const v = Number(data?.favorite_count ?? 0) || 0;
        setAssets((s) => ({ ...s, favoriteCount: v }));
      })
      .catch(() => {});

    // F-02 铃铛红点（消息未读总数 ≥1 显示）
    api
      .get('/api/v1/notifications/unread-count')
      .then((res: any) => {
        const data = res?.data ?? res;
        const cnt = data?.data?.unreadCount ?? data?.unreadCount ?? data?.unread_count ?? 0;
        setUnread(Number(cnt) || 0);
      })
      .catch(() => setUnread(0));
  }, [visible, loadHistories]);

  // 抽屉关闭时重置交互态
  useEffect(() => {
    if (!visible) {
      setMenuOpenId(null);
      setMenuAnchorRect(null);
      setSwipeOpenId(null);
      setManageMode(false);
      setSelectedIds(new Set());
    }
  }, [visible]);

  // [BUG-461 Fix-A] 「点击菜单外区域自动关闭」全局监听
  // 仅在菜单打开时挂载；点击事件冒泡到 document 时，若目标不在菜单 DOM 内部，
  // 则关闭菜单。同时监听滚动 / 窗口尺寸变化，菜单也应关闭，避免悬空。
  useEffect(() => {
    if (!menuOpenId) return;
    const closeMenu = () => {
      setMenuOpenId(null);
      setMenuAnchorRect(null);
    };
    const onDocPointerDown = (e: Event) => {
      const node = menuRef.current;
      if (node && node.contains(e.target as Node)) return; // 点在菜单内部 → 保留
      closeMenu();
    };
    // 使用 capture=true 以更早接到事件，避免被 stopPropagation 吞掉
    document.addEventListener('mousedown', onDocPointerDown, true);
    document.addEventListener('touchstart', onDocPointerDown, true);
    window.addEventListener('resize', closeMenu);
    // 历史列表滚动容器内滚动时也关闭菜单
    document.addEventListener('scroll', closeMenu, true);
    return () => {
      document.removeEventListener('mousedown', onDocPointerDown, true);
      document.removeEventListener('touchstart', onDocPointerDown, true);
      window.removeEventListener('resize', closeMenu);
      document.removeEventListener('scroll', closeMenu, true);
    };
  }, [menuOpenId]);

  // [BUG-461 Fix-C 配套] 外部触发"历史对话刷新"事件后，主动重新拉取列表。
  // 例：用户在 chat 页切换咨询人 → 创建新会话成功后 dispatch 此事件，
  //     抽屉无需用户重新打开即可看到新条目。
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handler = () => {
      loadHistories();
    };
    window.addEventListener('bh-history-refresh', handler);
    return () => window.removeEventListener('bh-history-refresh', handler);
  }, [loadHistories]);

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

  /**
   * [PRD-463 2026-05-11] 点击「订单」格智能定位 Tab：
   *   - v2Receipt > v2Use            → 待收货 Tab (pending_receipt)
   *   - v2Receipt < v2Use            → 待使用 Tab (pending_use)
   *   - v2Receipt == v2Use 且都 > 0   → 待收货 Tab（业务紧急度更高）
   *   - 两者都为 0                    → 全部 Tab (all)
   */
  const handleOrderClick = () => {
    const r = assets.v2Receipt || 0;
    const u = assets.v2Use || 0;
    let tab: 'all' | 'pending_receipt' | 'pending_use' = 'all';
    if (r === 0 && u === 0) tab = 'all';
    else if (r >= u) tab = 'pending_receipt';
    else tab = 'pending_use';
    navigateTo(`/unified-orders?tab=${tab}`);
  };

  // ─────────────────── F-11 单条操作 ───────────────────
  // [BUG-457 Fix-1] 删除 ID 胶囊「📋 复制」入口与 handleCopyId 函数。
  // 整个胶囊改为跳转到个人资料编辑页 /profile/edit，
  // 用户如需复制 ID，可在编辑页中自行选中复制。
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

  // [BUG-462 (2026-05-11)] 单条删除修复：
  //  - 旧实现调用不存在的 `POST /api/chat/history/delete`，每次必然 4xx 进 catch，
  //    乐观更新虽然让条目视觉上消失，但数据库实际并未删除，刷新后被删条目"复活"，
  //    并弹出"删除可能未同步，请稍后刷新"的兜底 Toast。
  //  - 改为真实接口 `DELETE /api/chat-sessions/{id}`。
  //  - 失败时按"立刻回滚 + 友好提示"方案：保留删除前的完整 histories 快照，
  //    出错时 setHistories(snapshot) 整体恢复，并显示"删除失败,请稍后重试"。
  const deleteOne = async (id: string) => {
    setMenuOpenId(null);
    setSwipeOpenId(null);
    const ok = await Dialog.confirm({
      content: '确认删除该对话？',
      confirmText: '确认',
      cancelText: '取消',
    });
    if (!ok) return;

    const snapshot = histories;
    setHistories((prev) => prev.filter((h) => h.id !== id));

    try {
      await api.delete(`/api/chat-sessions/${id}`);
      // [AI对话模式优化 PRD v1.0 §7] 改走统一 Toast：水平居中 + 上方 1/3 + 绿色/对勾
      ToastUnified.success('已删除');
    } catch {
      setHistories(snapshot);
      ToastUnified.fail('删除失败,请稍后重试');
    }
  };

  // ─────────────────── F-12 批量删除 ───────────────────
  // [BUG-462 (2026-05-11)] 批量删除修复：
  //  - 旧实现调用不存在的 `POST /api/chat/history/delete`，必然 4xx，
  //    与单条删除同样的问题（视觉消失但实际未删 + 兜底 Toast）。
  //  - 改为真实接口 `POST /api/chat-sessions/batch-delete`，请求体字段为
  //    `session_ids`（后端 `List[int]`，前端 id 为字符串 → 转 number 后下发）。
  //  - 失败时：恢复 histories 快照 + 保留管理模式 + 保留勾选状态 + 友好提示，
  //    让用户可以原地重试或调整选择。
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

    const snapshotHistories = histories;
    const snapshotSelectedIds = new Set(selectedIds);

    setHistories((prev) => prev.filter((h) => !selectedIds.has(h.id)));
    setSelectedIds(new Set());
    setManageMode(false);

    try {
      const sessionIds = ids
        .map((s) => Number(s))
        .filter((n) => Number.isFinite(n));
      await api.post('/api/chat-sessions/batch-delete', {
        session_ids: sessionIds,
      });
      Toast.show({ content: '已删除', icon: 'success' });
    } catch {
      setHistories(snapshotHistories);
      setSelectedIds(snapshotSelectedIds);
      setManageMode(true);
      Toast.show({ content: '删除失败,请稍后重试', icon: 'fail' });
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
    // [BUG-461 Fix-A] menuVisible 不再用于渲染内联菜单（菜单已 Portal 化）
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
                // [BUG-461 Fix-A] 记录按钮 DOMRect，供 Portal 菜单基于按钮位置计算
                if (menuOpenId === item.id) {
                  setMenuOpenId(null);
                  setMenuAnchorRect(null);
                } else {
                  const btn = e.currentTarget as HTMLButtonElement;
                  setMenuAnchorRect(btn.getBoundingClientRect());
                  setMenuOpenId(item.id);
                }
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
        {/* [BUG-461 Fix-A] F-11 ⋯ 菜单已挪到组件根部统一通过 Portal 渲染，此处不再渲染内联菜单 */}
      </div>
    );
  };

  /**
   * [BUG-461 Fix-A] ⋯ 菜单 Portal 渲染：
   *   - 渲染到 document.body 最外层，z-index = 9999
   *   - 位置基于 menuAnchorRect 计算：默认置于按钮下方右对齐
   *   - 菜单下方空间不足时（距离视口底部 < menuHeightEstimate）向上翻转
   *   - 距离视口左边过近时左对齐到按钮左侧
   * 注意：必须保证仅在浏览器环境且菜单打开时才调用 createPortal。
   */
  const renderHistoryMenuPortal = () => {
    if (typeof document === 'undefined') return null;
    if (!menuOpenId || !menuAnchorRect || manageMode) return null;
    const item = histories.find((h) => h.id === menuOpenId);
    if (!item) return null;

    const MENU_WIDTH = 120;
    const MENU_HEIGHT_ESTIMATE = 90; // 两行 + 分隔线，约 90px
    const SAFE_MARGIN = 8;

    const vw = typeof window !== 'undefined' ? window.innerWidth : 360;
    const vh = typeof window !== 'undefined' ? window.innerHeight : 640;

    // 水平：默认右对齐到按钮右边缘；右边超出则向左收
    let left = menuAnchorRect.right - MENU_WIDTH;
    if (left + MENU_WIDTH > vw - SAFE_MARGIN) {
      left = vw - MENU_WIDTH - SAFE_MARGIN;
    }
    if (left < SAFE_MARGIN) left = SAFE_MARGIN;

    // 垂直：默认按钮下方；底部空间不足则向上翻转（出现在按钮上方）
    let top = menuAnchorRect.bottom + 4;
    if (top + MENU_HEIGHT_ESTIMATE > vh - SAFE_MARGIN) {
      top = menuAnchorRect.top - MENU_HEIGHT_ESTIMATE - 4;
      if (top < SAFE_MARGIN) top = SAFE_MARGIN;
    }

    const node = (
      <div
        ref={menuRef}
        style={{
          position: 'fixed',
          left,
          top,
          width: MENU_WIDTH,
          background: COLOR.cardBg,
          borderRadius: 8,
          boxShadow: '0 6px 20px rgba(0,0,0,0.18)',
          zIndex: 9999,
          overflow: 'hidden',
          border: `1px solid ${COLOR.divider}`,
        }}
        data-testid="bh-history-menu"
        onMouseDown={(e) => e.stopPropagation()}
        onTouchStart={(e) => e.stopPropagation()}
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
          data-testid="bh-history-menu-pin"
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
          data-testid="bh-history-menu-delete"
        >
          删除
        </button>
      </div>
    );

    return ReactDOM.createPortal(node, document.body);
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
          {/* ─── F-01 顶栏：头像 + 名片块（昵称+ID）+ 顶栏图标（同一行） ─── */}
          {/*
            [BUG-458 (2026-05-11)] 顶栏布局重构：
            把原本「头像/图标」第一行 + 「昵称」第二行 + 「ID 胶囊」第三行的纵向堆叠，
            改为 单行 Flex：头像（固定）│ 名片块（弹性，内部纵向：昵称 + ID 胶囊）│ 顶栏图标组（固定，右对齐）。
            同时按 BUG 文档 R-09 取消 ID 胶囊的点击复制功能（仅作纯展示，不响应点击、不显示复制图标、不显示 Toast、不展示 cursor:pointer）。
          */}
          <div
            style={{
              padding: '12px 16px 8px 16px',
              paddingTop: 'max(12px, calc(env(safe-area-inset-top) + 8px))',
              flexShrink: 0,
            }}
            data-testid="bh-sidebar-top"
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}
              data-testid="bh-sidebar-top-row"
            >
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

              {/* 中：名片块（昵称 + ID 胶囊，纵向两行）—— flex:1 + min-width:0 保证 ellipsis 可生效 */}
              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  gap: 4,
                }}
                data-testid="bh-user-nameblock"
              >
                <div
                  style={{
                    fontSize: 16,
                    fontWeight: 700,
                    color: COLOR.textPrimary,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    lineHeight: 1.2,
                  }}
                  data-testid="bh-user-nickname"
                >
                  {user?.nickname || '未登录'}
                </div>
                {/* [BUG-458 R-09] ID 胶囊：纯展示，不响应点击、无复制图标、无 Toast、无 cursor:pointer */}
                <div
                  style={{
                    display: 'inline-flex',
                    alignSelf: 'flex-start',
                    alignItems: 'center',
                    maxWidth: '100%',
                    padding: '2px 10px',
                    background: COLOR.capsuleBg,
                    borderRadius: 10,
                    fontSize: 12,
                    lineHeight: '16px',
                    color: COLOR.capsuleText,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  data-testid="bh-id-capsule"
                >
                  <span
                    style={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    ID: {idDisplay}
                  </span>
                </div>
              </div>

              {/* 右：顶栏图标组（固定宽，右对齐，垂直居中对齐名片块） */}
              <div
                style={{
                  flexShrink: 0,
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
                {/* [BUG-457 Fix-2] 已删除中间「⊞ 会员二维码」入口（PRD-455 F-03） */}
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
          </div>

          {/* 内容区：仅历史对话可滚动；顶部用户卡片 + 资产 + 高频入口固定（F-14） */}
          <div
            style={{
              padding: '0 16px',
              flexShrink: 0,
            }}
          >
            {/*
              [PRD-463 2026-05-11] F-06 资产行四并列 · 展示优化：
                1. 视觉风格统一：四格全部采用「大号数字 + 下方文字」展示，去除优惠券/订单 emoji 图标
                2. 顺序调整：积分 → 优惠券 → 收藏 → 订单（收藏与订单互换）
                3. 数字展示：优惠券/收藏/订单 应用 formatBadge（0 显示 0，1~9 显示真实数字，≥10 显示 9+）
                   积分保留原始数字，不应用截断
                4. 订单点击智能定位 Tab，详见 handleOrderClick
            */}
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
              {/* 1. 积分 — [AI对话模式优化 PRD v1.0 §8.1] 修复 404：/points-center → /points（新版积分主页） */}
              <div
                style={{ flex: 1, textAlign: 'center', cursor: 'pointer' }}
                onClick={() => navigateTo('/points')}
                data-testid="bh-asset-points"
              >
                <div style={{ fontSize: 16, fontWeight: 700, color: COLOR.textPrimary, lineHeight: 1.2 }}>
                  {assets.points}
                </div>
                <div style={{ fontSize: 12, color: COLOR.textSecondary, marginTop: 4 }}>积分</div>
              </div>
              {/* 2. 优惠券（统一数字风格） */}
              <div
                style={{ flex: 1, textAlign: 'center', cursor: 'pointer' }}
                onClick={() => navigateTo('/my-coupons')}
                data-testid="bh-asset-coupons"
              >
                <div style={{ fontSize: 16, fontWeight: 700, color: COLOR.textPrimary, lineHeight: 1.2 }}>
                  {formatBadge(assets.couponCount)}
                </div>
                <div style={{ fontSize: 12, color: COLOR.textSecondary, marginTop: 4 }}>优惠券</div>
              </div>
              {/* 3. 收藏（统一数字风格；顺序上移到订单前） */}
              <div
                style={{ flex: 1, textAlign: 'center', cursor: 'pointer' }}
                onClick={() => navigateTo('/my-favorites')}
                data-testid="bh-asset-favorites"
              >
                <div style={{ fontSize: 16, fontWeight: 700, color: COLOR.textPrimary, lineHeight: 1.2 }}>
                  {formatBadge(assets.favoriteCount)}
                </div>
                <div style={{ fontSize: 12, color: COLOR.textSecondary, marginTop: 4 }}>收藏</div>
              </div>
              {/* 4. 订单（统一数字风格 + 智能定位 Tab；顺序下移到收藏之后） */}
              <div
                style={{ flex: 1, textAlign: 'center', cursor: 'pointer' }}
                onClick={handleOrderClick}
                data-testid="bh-asset-orders"
              >
                <div style={{ fontSize: 16, fontWeight: 700, color: COLOR.textPrimary, lineHeight: 1.2 }}>
                  {formatBadge(assets.orderCount)}
                </div>
                <div style={{ fontSize: 12, color: COLOR.textSecondary, marginTop: 4 }}>订单</div>
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

            {/* [BUG-457 Fix-4] 网络异常态：仅当 loadHistories 真正 reject 时进入；
                显示「加载失败，点击重试」按钮，点击后复用同一加载函数 */}
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
                <div style={{ marginBottom: 8 }}>加载失败</div>
                <button
                  onClick={() => {
                    setHistories([]);
                    loadHistories();
                  }}
                  style={{
                    background: 'transparent',
                    border: `1px solid ${COLOR.primary}`,
                    color: COLOR.primary,
                    cursor: 'pointer',
                    fontSize: 13,
                    padding: '4px 14px',
                    borderRadius: 14,
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

      {/* [BUG-461 Fix-A] ⋯ 菜单 Portal 渲染入口 */}
      {renderHistoryMenuPortal()}
    </>
  );
}
