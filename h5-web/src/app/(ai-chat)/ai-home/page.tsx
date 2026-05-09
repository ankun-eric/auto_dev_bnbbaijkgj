'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Toast, Swiper, Dialog } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { createChatSession } from '@/lib/chat-session';
import Sidebar from '@/components/ai-chat/Sidebar';
import MoreMenu from '@/components/ai-chat/MoreMenu';
import ConsultTargetPicker, { type FamilyMemberItem } from '@/components/ai-chat/ConsultTargetPicker';
// [PRD-426] 已移除 RecommendCards：原仅服务于"+ 选择咨询人"浮层；首页推荐问改用常驻横向胶囊（见下方 recommended 区块）
import SharePanel from '@/components/ai-chat/SharePanel';
import SectionErrorBoundary from '@/components/SectionErrorBoundary';
import DraggablePunchCard from '@/components/ai-chat/DraggablePunchCard';
import ProfileCard, { clearProfileCardCache } from '@/components/ai-chat/ProfileCard';
import ReminderBellButton from '@/components/ai-chat/ReminderBellButton';
import ReminderDrawer from '@/components/ai-chat/ReminderDrawer';
import { trackEvent, aiChatTrack, type AiChatTargetType } from '@/lib/analytics';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  time: string;
  isStreaming?: boolean;
  /** [PRD-432] 该消息绑定的咨询对象 family_member_id，AI 回答顶部档案卡片用 */
  consultantTargetId?: number | null;
  /** [PRD-433 F-14] 参考资料：仅当数组非空时渲染，接口未返回则不显示 */
  references?: Array<{ title: string; url?: string }>;
}

interface Banner {
  id: number;
  image_url: string;
  link_url?: string;
  title?: string;
}

interface FunctionButton {
  id: string;
  name: string;
  icon?: string;
  button_type: string;
  params?: Record<string, any>;
}

interface FamilyMember {
  id: number;
  nickname: string;
  relationship_type?: string;
  relation_type_name?: string;
  avatar?: string;
  is_self: boolean;
}

const FUNCTION_ROUTES: Record<string, string> = {
  'view_report': '/checkup',
  'check_drug': '/drug',
  'view_archive': '/health-archive',
  'check_order': '/unified-orders',
  'find_expert': '/service',
  'find_service': '/service',
};

const FUNCTION_ICONS: Record<string, string> = {
  'view_report': '📋',
  'check_drug': '💊',
  'view_archive': '📁',
  'check_order': '📦',
  'find_expert': '👨‍⚕️',
  'find_service': '🏥',
};

const DIALOG_TRIGGERS = new Set(['view_report', 'check_drug']);

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

// ─── PRD-405 AI 对话首页配置 类型与默认值（v1.0） ───────────────
interface FuncGridItemCfg {
  id?: string;
  main_text: string;
  sub_text: string;
  target_path: string;
  icon: string;
  icon_image_url?: string;
  gradient_start: string;
  gradient_end: string;
  badge?: string;
  enabled: boolean;
  sort: number;
}

// [PRD-425] AI 助手昵称配置（取自 ai_home_config.ai_chat.signature）
interface AIChatSignatureCfg {
  signature?: string;
}

interface AIHomeConfig {
  ai_chat?: AIChatSignatureCfg;
  welcome: {
    avatar: { type: 'emoji' | 'image'; emoji?: string; image_url?: string };
    greetings: { morning: string[]; afternoon: string[]; evening: string[] };
    subtitles: string[];
    show_nickname: boolean;
    main_title: string;
    sub_title: string;
  };
  topbar: {
    title: string;
    logo: { type: 'emoji' | 'image'; emoji?: string; image_url?: string };
    show_sidebar: boolean;
    show_more_menu: boolean;
    show_share: boolean;
    visible: boolean;
  };
  input: {
    placeholder: string;
    enable_voice: boolean;
    enable_tts: boolean;
    tts_provider: 'auto' | 'cloud' | 'browser';
    family_consult: {
      enabled: boolean;
      template: string;
      show_archive_link: boolean;
      archive_path: string;
    };
  };
  session: {
    idle_timeout_minutes: number;
    auto_new_session: boolean;
    empty_session_welcome: { enabled: boolean; messages: string[] };
    strategy: {
      max_answer_chars: number;
      show_loading: boolean;
      daily_free_quota: number;
      answer_style: 'professional' | 'easy' | 'friendly';
      sensitive_filter: boolean;
      context_memory_rounds: 3 | 5 | 10 | 20;
      disclaimer: string;
    };
  };
  floating_button: {
    enabled: boolean;
    icon: string;
    label?: string;
    show_label: boolean;
    target_path: string;
    position: 'right_bottom' | 'left_bottom';
  };
  banner: { visible: boolean };
  health_tips: { visible: boolean; interval_seconds: number; show_indicator: boolean };
  func_grid: { visible: boolean; columns: 2 | 3 | 4; max_count: number; items: FuncGridItemCfg[] };
  quick_tags: { visible: boolean; max_count: number };
  recommended_questions: Array<{
    id: string;
    icon: string;
    icon_image_url?: string;
    title: string;
    question: string;
    enabled: boolean;
    sort: number;
  }>;
  empty_placeholder: { icon: string; icon_image_url?: string; main_title: string };
  global_switches: {
    welcome_visible: boolean;
    health_tips_visible: boolean;
    func_grid_visible: boolean;
    recommended_visible: boolean;
    empty_placeholder_visible: boolean;
    family_pill_visible: boolean;
    archive_link_visible: boolean;
    voice_input_visible: boolean;
    floating_button_visible: boolean;
  };
}

const FALLBACK_CONFIG: AIHomeConfig = {
  welcome: {
    avatar: { type: 'emoji', emoji: '🌿' },
    greetings: { morning: ['早上好'], afternoon: ['午安'], evening: ['晚上好'] },
    subtitles: ['我是您的AI健康顾问小康'],
    show_nickname: true,
    main_title: '早上好，{昵称}！',
    sub_title: '我是您的AI健康顾问小康',
  },
  topbar: {
    title: 'AI 健康助手',
    logo: { type: 'emoji', emoji: '🌿' },
    show_sidebar: true,
    show_more_menu: true,
    show_share: true,
    visible: false,
  },
  input: {
    placeholder: '发消息或按住说话...',
    enable_voice: true,
    enable_tts: true,
    tts_provider: 'auto',
    family_consult: {
      enabled: true,
      template: '为({name})咨询',
      show_archive_link: true,
      archive_path: '/health-records',
    },
  },
  session: {
    idle_timeout_minutes: 30,
    auto_new_session: true,
    empty_session_welcome: { enabled: false, messages: [] },
    strategy: {
      max_answer_chars: 1000,
      show_loading: true,
      daily_free_quota: 50,
      answer_style: 'friendly',
      sensitive_filter: true,
      context_memory_rounds: 5,
      disclaimer: '以上内容仅供参考，不能替代医生诊疗',
    },
  },
  floating_button: {
    enabled: true,
    icon: '✅',
    label: '健康打卡',
    show_label: true,
    target_path: '/health-plan',
    position: 'right_bottom',
  },
  banner: { visible: true },
  health_tips: { visible: true, interval_seconds: 4, show_indicator: true },
  func_grid: {
    visible: true,
    columns: 3,
    max_count: 6,
    items: [
      { id: 'g1', main_text: 'AI诊室', sub_text: '智能问诊', target_path: '/ai-doctor', icon: '🩺', gradient_start: '#5B6CFF', gradient_end: '#8B9AFF', badge: '', enabled: true, sort: 1 },
      { id: 'g2', main_text: '看报告', sub_text: '解读体检报告', target_path: '/checkup', icon: '📋', gradient_start: '#FF7E5F', gradient_end: '#FEB47B', badge: '', enabled: true, sort: 2 },
      { id: 'g3', main_text: '健康档案', sub_text: '查看个人档案', target_path: '/health-archive', icon: '📁', gradient_start: '#43E97B', gradient_end: '#38F9D7', badge: '', enabled: true, sort: 3 },
    ],
  },
  quick_tags: { visible: true, max_count: 8 },
  recommended_questions: [
    { id: 'r1', icon: '📋', title: '体检解读', question: '帮我解读最新体检报告', enabled: true, sort: 1 },
    { id: 'r2', icon: '💊', title: '用药咨询', question: '感冒了吃什么药比较好？', enabled: true, sort: 2 },
    { id: 'r3', icon: '🥗', title: '饮食建议', question: '高血压患者饮食注意什么？', enabled: true, sort: 3 },
    { id: 'r4', icon: '💚', title: '失眠', question: '最近总是失眠怎么办？', enabled: true, sort: 4 },
  ],
  empty_placeholder: { icon: '💬', main_title: '还没有对话记录' },
  // [PRD-425] AI 助手昵称兜底"小康"
  ai_chat: { signature: '小康' },
  global_switches: {
    welcome_visible: true,
    health_tips_visible: true,
    func_grid_visible: true,
    recommended_visible: true,
    empty_placeholder_visible: true,
    family_pill_visible: true,
    archive_link_visible: true,
    voice_input_visible: true,
    floating_button_visible: true,
  },
};

function pickRandom<T>(arr: T[], fallback: T): T {
  if (!Array.isArray(arr) || arr.length === 0) return fallback;
  return arr[Math.floor(Math.random() * arr.length)];
}

function getGreetingByConfig(cfg: AIHomeConfig): string {
  const h = new Date().getHours();
  let pool: string[];
  if (h >= 5 && h < 12) pool = cfg.welcome.greetings.morning;
  else if (h >= 12 && h < 18) pool = cfg.welcome.greetings.afternoon;
  else pool = cfg.welcome.greetings.evening;
  return pickRandom(pool, '您好');
}

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 6) return '夜深了，注意休息';
  if (h < 9) return '早上好';
  if (h < 12) return '上午好';
  if (h < 14) return '中午好';
  if (h < 18) return '下午好';
  return '晚上好';
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  return `${hh}:${mm}`;
}

// [PRD-433 F-09] 微信式时间分隔条文案：今天 HH:mm / 昨天 HH:mm / 周X HH:mm / YYYY/MM/DD HH:mm
function formatWeChatTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfYesterday = startOfToday - 86400000;
  const startOfWeek = startOfToday - 6 * 86400000;
  const t = d.getTime();
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  const time = `${hh}:${mm}`;
  if (t >= startOfToday) return `今天 ${time}`;
  if (t >= startOfYesterday) return `昨天 ${time}`;
  if (t >= startOfWeek) {
    const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return `${weekDays[d.getDay()]} ${time}`;
  }
  const yyyy = d.getFullYear();
  const mo = (d.getMonth() + 1).toString().padStart(2, '0');
  const dd = d.getDate().toString().padStart(2, '0');
  return `${yyyy}/${mo}/${dd} ${time}`;
}

function shouldShowTime(prev: string | null, curr: string): boolean {
  if (!prev) return true;
  return new Date(curr).getTime() - new Date(prev).getTime() > 5 * 60 * 1000;
}

function renderMarkdown(text: string): string {
  let html = text
    .replace(/\r\n/g, '\n')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  html = html.replace(/^###\s+(.+?)\s*$/gm, '<h3 style="font-size:15px;font-weight:bold;margin-top:10px;margin-bottom:4px">$1</h3>');
  html = html.replace(/^##\s+(.+?)\s*$/gm, '<h2 style="font-size:16px;font-weight:bold;margin-top:12px;margin-bottom:4px">$1</h2>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/`(.+?)`/g, '<code style="background:#E8E8F0;padding:1px 4px;border-radius:3px;font-size:12px">$1</code>');
  html = html.replace(/^- (.+)$/gm, '<li style="margin-left:16px;list-style:disc">$1</li>');
  html = html.replace(/^(\d+)\. (.+)$/gm, '<li style="margin-left:16px;list-style:decimal">$2</li>');
  html = html.replace(/\n/g, '<br/>');
  return html;
}

export default function AiHomePage() {
  const router = useRouter();
  const { user } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [consultantOpen, setConsultantOpen] = useState(false);

  // [PRD-439 F-02/F-04] 提醒抽屉 + 徽标
  const [reminderOpen, setReminderOpen] = useState(false);
  const [reminderBadge, setReminderBadge] = useState(0);

  const refreshReminderBadge = useCallback(async () => {
    try {
      const res: any = await api.get('/api/medication-reminder/badge');
      const total = (res?.total ?? res?.data?.total ?? 0) as number;
      setReminderBadge(Number.isFinite(total) ? total : 0);
    } catch {
      // 未登录或接口异常时静默：徽标显示 0（即不展示）
      setReminderBadge(0);
    }
  }, []);

  // 顶部欢迎面板（欢迎区/健康贴士/功能宫格/推荐问）改为常驻瀑布流：
  // 始终位于文档流顶部，与消息列表一起自然向下排布、整体滚动；
  // 不再有折叠态、不再有右上角圆形小康头像悬浮按钮、不再有"收起/展开"切换。
  const messageScrollRef = useRef<HTMLDivElement>(null);

  const [banners, setBanners] = useState<Banner[]>([]);
  const [funcButtons, setFuncButtons] = useState<FunctionButton[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  // [PRD-426] 已移除 inputFocused 状态：原仅用于控制"+ 选择咨询人"浮层显隐，浮层删除后无需此状态
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [hasHealthTask, setHasHealthTask] = useState(false);
  const [selectedConsultant, setSelectedConsultant] = useState<FamilyMember | null>(null);
  const [idleTimeout, setIdleTimeout] = useState<number>(30 * 60 * 1000);
  // [Bug-433] lastMsgTime 改为 useRef：避免 React state 异步更新导致 handleSend
  // 在闭包中读到的旧值，从而错误命中"空闲超时清空消息"分支，造成会话首句丢失。
  // 任何写入 setLastMsgTime() 的位置都同步更新此 ref，保证语音/预设按钮等异步入口
  // 在闭包中也能读到最新时间戳。
  const lastMsgTimeRef = useRef<number>(0);
  const [lastMsgTime, setLastMsgTimeState] = useState<number>(0);
  const setLastMsgTime = useCallback((t: number) => {
    lastMsgTimeRef.current = t;
    setLastMsgTimeState(t);
  }, []);
  const [voiceMode, setVoiceMode] = useState(false);
  const [recording, setRecording] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
  const [recordStartY, setRecordStartY] = useState(0);
  const [recordCancelled, setRecordCancelled] = useState(false);
  const [volumeLevel, setVolumeLevel] = useState(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);

  // PRD-405：从后端读取 AI 首页配置（带 5 分钟本地缓存 + 内置兜底）
  const [aiHomeConfig, setAiHomeConfig] = useState<AIHomeConfig>(FALLBACK_CONFIG);

  // [PRD-425] 通知中心未读总数（进入页面拉一次；接口异常 → null 表示不显示徽标）
  const [unreadCount, setUnreadCount] = useState<number | null>(null);
  // 同一会话期内固定的随机选择
  const [pickedGreeting, setPickedGreeting] = useState<string>('');
  const [pickedSubtitle, setPickedSubtitle] = useState<string>('');

  // [PRD-420] 切换咨询对象后的「返回上一会话」5 秒撤销栈
  // 记录切换前的会话 id 与咨询对象，5 秒内点击「返回上一会话」可恢复
  const [undoSnapshot, setUndoSnapshot] = useState<{
    sessionId: string | null;
    consultant: FamilyMemberItem | null;
    messages: ChatMessage[];
    expiresAt: number;
  } | null>(null);
  const [undoToastVisible, setUndoToastVisible] = useState(false);
  const [undoToastText, setUndoToastText] = useState('');
  const undoTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const recommendQuestions = (aiHomeConfig.recommended_questions || [])
    .filter((q) => q.enabled)
    .sort((a, b) => (a.sort || 0) - (b.sort || 0))
    .slice(0, 8)
    .map((q) => ({ tag: q.title || q.icon, text: q.question }));

  useEffect(() => {
    if (typeof window !== 'undefined' && navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function') {
      setVoiceSupported(true);
    }
  }, []);

  useEffect(() => {
    api.get('/api/h5/home-banners').then((res: any) => {
      const data = res.data || res;
      setBanners(Array.isArray(data.items) ? data.items : []);
    }).catch(() => {});

    api.get('/api/function-buttons').then((res: any) => {
      const data = res.data || res;
      setFuncButtons(Array.isArray(data.items) ? data.items : []);
    }).catch(() => {});

    api.get('/api/health-plan/today-tasks').then((res: any) => {
      const data = res.data || res;
      setHasHealthTask(!!data.has_tasks);
    }).catch(() => {});

    // [PRD-439 F-02] 提醒徽标：用药未打卡数 + 待核销订单数
    refreshReminderBadge();

    api.get('/api/app-settings/chat-idle-timeout').then((res: any) => {
      const data = res.data || res;
      if (data.timeout_ms) setIdleTimeout(data.timeout_ms);
      else if (data.timeout_minutes) setIdleTimeout(data.timeout_minutes * 60 * 1000);
    }).catch(() => {});

    // PRD-405：拉取 AI 对话首页配置（带 5 分钟本地缓存 + 内置兜底）
    // [Bug-419 H-5/H-8 2026-05-08] 把原来的浅合并 `{ ...FALLBACK, ...data }` 换成
    // 顶层 key 级深合并：避免后端任一模块返回 `{}`/缺字段时把 FALLBACK_CONFIG
    // 的整组默认值覆盖掉，从而读取 deep field（如 welcome.greetings.morning）抛
    // `Cannot read properties of undefined` → ai-home 整页白屏。
    (async () => {
      const CACHE_KEY = '__ai_home_config_cache__';
      const TTL = 5 * 60 * 1000;
      const mergeWithFallback = (data: any): AIHomeConfig => {
        const out: any = { ...FALLBACK_CONFIG };
        if (data && typeof data === 'object') {
          Object.keys(data).forEach((k) => {
            const v = (data as any)[k];
            const fb = (FALLBACK_CONFIG as any)[k];
            if (v && typeof v === 'object' && !Array.isArray(v) && fb && typeof fb === 'object' && !Array.isArray(fb)) {
              out[k] = { ...fb, ...v };
            } else if (v !== undefined && v !== null) {
              out[k] = v;
            }
          });
        }
        return out as AIHomeConfig;
      };
      try {
        let cached: { config: AIHomeConfig; ts: number } | null = null;
        if (typeof window !== 'undefined') {
          try {
            const raw = localStorage.getItem(CACHE_KEY);
            if (raw) cached = JSON.parse(raw);
          } catch {}
        }
        let cfg: AIHomeConfig | null = null;
        if (cached && Date.now() - cached.ts < TTL && cached.config) {
          // 缓存数据也走一遍兜底 merge，防止旧缓存缺字段（兼容线上历史脏缓存）
          cfg = mergeWithFallback(cached.config);
        }
        if (!cfg) {
          try {
            const res: any = await api.get('/api/ai-home-config');
            const data = res?.data?.config || res?.config || null;
            cfg = mergeWithFallback(data);
            try {
              localStorage.setItem(CACHE_KEY, JSON.stringify({ config: cfg, ts: Date.now() }));
            } catch {}
          } catch {
            // [Bug-419 H-8] 接口失败时直接使用内置完整默认配置，保持首页骨架完整
            cfg = { ...FALLBACK_CONFIG };
          }
        }
        setAiHomeConfig(cfg!);
      } catch {
        // 任何意外异常都不让首页崩塌：使用兜底配置
        setAiHomeConfig({ ...FALLBACK_CONFIG });
      }
    })();
  }, []);

  // 同一会话期内随机选定问候语和副标题（仅在配置加载完成后执行一次）
  useEffect(() => {
    if (!pickedGreeting) {
      setPickedGreeting(getGreetingByConfig(aiHomeConfig));
    }
    if (!pickedSubtitle) {
      setPickedSubtitle(pickRandom(aiHomeConfig.welcome?.subtitles || [], '我是您的AI健康助手'));
    }
    // 同步空闲超时（如果新配置下发更短/更长）
    const m = aiHomeConfig.session?.idle_timeout_minutes;
    if (m && m > 0) setIdleTimeout(m * 60 * 1000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiHomeConfig]);

  // PRD-405 F-11：空会话引导（不入库，仅 UI 提示）
  useEffect(() => {
    const cfg = aiHomeConfig.session?.empty_session_welcome;
    if (
      cfg &&
      cfg.enabled &&
      Array.isArray(cfg.messages) &&
      cfg.messages.length > 0 &&
      !sessionId &&
      messages.length === 0
    ) {
      const text = pickRandom(cfg.messages, '');
      if (text) {
        setMessages([
          {
            id: `welcome-${Date.now()}`,
            role: 'assistant',
            content: text,
            time: new Date().toISOString(),
          },
        ]);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiHomeConfig, sessionId]);

  useEffect(() => {
    loadLastSession();
  }, []);

  // [PRD-425] 进入 /ai-home 时拉取一次通知中心未读总数；离开页面再回来视为重新进入
  // 失败 / 超时 / 未登录 → 保持 null，徽标不显示（按 PRD §5.2 异常兜底）
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = typeof window !== 'undefined' ? localStorage.getItem('token') : '';
        if (!token) return;
        const res: any = await api.get('/api/v1/notifications/unread-count');
        const data = res?.data ?? res;
        const cnt = data?.data?.unreadCount;
        if (!cancelled && typeof cnt === 'number' && cnt >= 0) {
          setUnreadCount(cnt);
        }
      } catch {
        // 接口异常静默：徽标不显示
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 收到新消息后滚动到底部最新消息（瀑布流自然滚动，菜单栏会被推到上方视野外）
  useEffect(() => {
    if (messages.length > 0) {
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' });
      });
    }
  }, [messages.length]);

  const loadLastSession = async () => {
    try {
      const res: any = await api.get('/api/chat/sessions', { params: { limit: 1, sort: '-updated_at' } });
      const data = res.data || res;
      const list = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : []);
      if (list.length > 0) {
        const session = list[0];
        const sid = String(session.id);
        setSessionId(sid);
        setLastMsgTime(new Date(session.updated_at || session.created_at).getTime());
        await loadSessionMessages(sid);
      }
    } catch {}
  };

  const loadSessionMessages = async (sid: string) => {
    try {
      const res: any = await api.get(`/api/chat/sessions/${sid}/messages`);
      const data = res.data || res;
      const list = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : []);
      if (list.length > 0) {
        const mapped: ChatMessage[] = list.map((m: any) => ({
          id: String(m.id),
          role: m.role === 'user' ? 'user' as const : 'assistant' as const,
          content: m.content || '',
          time: m.created_at || new Date().toISOString(),
        }));
        setMessages(mapped);
      }
    } catch {}
  };

  const createNewSession = async (): Promise<string | null> => {
    // [Bug-419 H-1/H-2] 走统一 createChatSession 工具，自动补齐 session_type=health_qa
    // 并把字段名规范化为 family_member_id（修复历史 member_id 字段名错误导致的 422）。
    // 工具内部已 try/catch + Toast，不会向上抛异常，避免触发 ai-home 整页白屏。
    const res = await createChatSession({
      session_type: 'health_qa',
      family_member_id: selectedConsultant ? selectedConsultant.id : undefined,
    });
    if (!res.ok || !res.sessionId) return null;
    setSessionId(res.sessionId);
    return res.sessionId;
  };

  // [Bug-433] checkIdleAndMaybeNewSession 接受可选的 preserveOnClear 回调：
  // 当命中"空闲超时清空消息"分支时，外部（handleSend）可以通过该参数把
  // 即将插入的乐观渲染 userMsg 回填到清空后的列表中，避免会话首句被一并清掉。
  // 同时 lastMsgTime 改为从 ref 读取，避免闭包过期导致的"语音/预设按钮首句"误清空。
  const checkIdleAndMaybeNewSession = async (
    preserveOnClear?: () => ChatMessage[],
  ): Promise<string> => {
    const now = Date.now();
    const lmt = lastMsgTimeRef.current;
    if (sessionId && lmt && (now - lmt) > idleTimeout) {
      const preserve = preserveOnClear ? preserveOnClear() : [];
      setMessages(preserve);
      const newSid = await createNewSession();
      return newSid || sessionId;
    }
    if (!sessionId) {
      const newSid = await createNewSession();
      return newSid || '';
    }
    return sessionId;
  };

  const sendSSE = async (
    sid: string,
    message: string,
    retries = 3,
    source: 'text' | 'voice' | 'preset' = 'text',
  ): Promise<boolean> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : '';
    const aiMsgId = `a-${Date.now()}`;
    const aiMsg: ChatMessage = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      time: new Date().toISOString(),
      isStreaming: true,
    };
    setMessages(prev => [...prev, aiMsg]);

    for (let attempt = 0; attempt < retries; attempt++) {
      try {
        const controller = new AbortController();
        abortRef.current = controller;

        const response = await fetch(`${basePath}/api/chat/sessions/${sid}/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({ content: message, message_type: 'text', source }),
          signal: controller.signal,
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No reader');

        const decoder = new TextDecoder();
        let accumulated = '';
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const payload = line.substring(6);
              if (payload === '[DONE]') break;
              try {
                const parsed = JSON.parse(payload);
                if (parsed.content) {
                  accumulated += parsed.content;
                  setMessages(prev => prev.map(m =>
                    m.id === aiMsgId ? { ...m, content: accumulated } : m
                  ));
                }
              } catch {}
            }
          }
        }

        setMessages(prev => prev.map(m =>
          m.id === aiMsgId ? { ...m, isStreaming: false } : m
        ));
        abortRef.current = null;
        return true;
      } catch (err: any) {
        if (err.name === 'AbortError') {
          setMessages(prev => prev.map(m =>
            m.id === aiMsgId ? { ...m, isStreaming: false } : m
          ));
          return true;
        }
        if (attempt === retries - 1) {
          setMessages(prev => prev.filter(m => m.id !== aiMsgId));
          return false;
        }
        await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
      }
    }
    return false;
  };

  const sendFallback = async (
    sid: string,
    message: string,
    source: 'text' | 'voice' | 'preset' = 'text',
  ) => {
    try {
      const res: any = await api.post(`/api/chat/sessions/${sid}/messages`, {
        content: message,
        message_type: 'text',
        source,
      });
      const data = res.data || res;
      const aiMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: data.reply || data.content || data.message || '抱歉，我暂时无法回复',
        time: new Date().toISOString(),
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch {
      setMessages(prev => [...prev, {
        id: `e-${Date.now()}`,
        role: 'assistant',
        content: '网络异常，请稍后重试',
        time: new Date().toISOString(),
      }]);
    }
  };

  // [Bug-433] 统一发送入口：文字 / 语音 / 预设问题快捷按钮全部走 handleSend。
  // 关键修复（解决会话首句丢失 P0）：
  //   1. 立即更新 lastMsgTimeRef.current → 确保后续异步入口（语音 onstop / 预设
  //      按钮 onClick）读到的"最近消息时间"是最新值，不再因 React state 闭包过期
  //      错误命中"空闲超时清空"分支。
  //   2. 把 idle 判断 + sid 决定提前到"加入 userMsg 之前"，并通过 preserveOnClear
  //      回调把 userMsg 回填到清空后的列表，从源头杜绝首句被一并抹掉。
  //   3. 透传 source（text/voice/preset）到后端流式接口，便于审计与回归。
  const handleSend = useCallback(async (
    text?: string,
    source: 'text' | 'voice' | 'preset' = 'text',
  ) => {
    const msg = text || inputValue.trim();
    if (!msg || sending) return;

    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = '24px';
    }

    setSending(true);
    // [Bug-433] 立即更新 ref，确保后续异步入口读取到最新值
    const sendAt = Date.now();
    lastMsgTimeRef.current = sendAt;
    setLastMsgTimeState(sendAt);

    // [PRD-423 T-08 EVT-10] 发送消息埋点
    const sendTargetType: AiChatTargetType = selectedConsultant ? 'family' : 'self';
    aiChatTrack.send(sendTargetType, {
      target_id: selectedConsultant?.id ?? null,
      target_name: selectedConsultant?.nickname ?? '本人',
      content_length: msg.length,
    });

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: msg,
      time: new Date().toISOString(),
    };

    try {
      // [Bug-433] 先决定 sid（idle 命中时清空消息），命中时通过 preserveOnClear
      // 把 userMsg 回填到清空后的列表，避免首句被一并抹掉。
      const sid = await checkIdleAndMaybeNewSession(() => [userMsg]);
      if (!sid) {
        setMessages(prev => (prev.some(m => m.id === userMsg.id) ? prev : [...prev, userMsg]));
        setMessages(prev => [...prev, {
          id: `e-${Date.now()}`,
          role: 'assistant',
          content: '创建会话失败，请重试',
          time: new Date().toISOString(),
        }]);
        setSending(false);
        return;
      }
      // 若 idle 未命中（preserveOnClear 未被调用），将 userMsg 追加到列表末尾；
      // 若 idle 命中已通过 preserveOnClear 回填，避免重复插入。
      setMessages(prev => (prev.some(m => m.id === userMsg.id) ? prev : [...prev, userMsg]));

      const sseOk = await sendSSE(sid, msg, 3, source);
      if (!sseOk) {
        await sendFallback(sid, msg, source);
      }
    } catch {
      setMessages(prev => (prev.some(m => m.id === userMsg.id) ? prev : [...prev, userMsg]));
      setMessages(prev => [...prev, {
        id: `e-${Date.now()}`,
        role: 'assistant',
        content: '网络异常，请稍后重试',
        time: new Date().toISOString(),
      }]);
    }
    setSending(false);
  }, [inputValue, sending, sessionId, selectedConsultant, idleTimeout]);

  const handleFuncButton = (btn: FunctionButton) => {
    const key = btn.button_type || btn.id;
    if (DIALOG_TRIGGERS.has(key)) {
      const route = FUNCTION_ROUTES[key] || '/';
      const cardMsg: ChatMessage = {
        id: `c-${Date.now()}`,
        role: 'assistant',
        content: `💡 点击前往${btn.name}：${route}`,
        time: new Date().toISOString(),
      };
      setMessages(prev => [...prev, cardMsg]);
    } else {
      const route = FUNCTION_ROUTES[key];
      if (route) router.push(route);
    }
  };

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    const el = e.target;
    el.style.height = '24px';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  };

  const mimeTypeRef = useRef('');
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);

  const getPreferredMimeType = (): string => {
    if (typeof MediaRecorder !== 'undefined') {
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus';
      if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4';
      if (MediaRecorder.isTypeSupported('audio/mp3')) return 'audio/mp3';
    }
    return '';
  };

  const mimeToFormat = (mime: string): string => {
    if (!mime) return 'webm';
    if (mime.includes('webm')) return 'webm';
    if (mime.includes('mp4')) return 'm4a';
    if (mime.includes('mp3') || mime.includes('mpeg')) return 'mp3';
    return 'webm';
  };

  const checkMicPermission = useCallback(async (): Promise<boolean> => {
    if (!navigator.mediaDevices?.getUserMedia) {
      Toast.show({ content: '当前浏览器不支持语音输入', icon: 'fail' });
      return false;
    }
    try {
      if (navigator.permissions) {
        const permStatus = await navigator.permissions.query({ name: 'microphone' as PermissionName });
        if (permStatus.state === 'granted') return true;
        if (permStatus.state === 'denied') {
          Toast.show({ content: '麦克风权限已被禁止，请在系统设置中开启', icon: 'fail', duration: 2500 });
          return false;
        }
      }
      const result = await Dialog.confirm({
        title: '允许访问麦克风',
        content: '需要使用麦克风进行语音输入，请授权',
        confirmText: '去授权',
        cancelText: '取消',
      });
      if (!result) return false;
      const testStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      testStream.getTracks().forEach(t => t.stop());
      return true;
    } catch {
      Toast.show({ content: '请在系统设置中开启麦克风权限', icon: 'fail', duration: 2500 });
      return false;
    }
  }, []);

  const handleMicToggle = useCallback(async () => {
    if (voiceMode) {
      setVoiceMode(false);
      return;
    }
    const granted = await checkMicPermission();
    if (granted) setVoiceMode(true);
  }, [voiceMode, checkMicPermission]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const mime = getPreferredMimeType();
      mimeTypeRef.current = mime;
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      const updateVolume = () => {
        if (!analyserRef.current) return;
        const data = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(data);
        const avg = data.reduce((a, b) => a + b, 0) / data.length;
        setVolumeLevel(Math.min(avg / 128, 1));
        animFrameRef.current = requestAnimationFrame(updateVolume);
      };
      updateVolume();

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        cancelAnimationFrame(animFrameRef.current);
        analyserRef.current = null;
        setVolumeLevel(0);
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(t => t.stop());
          streamRef.current = null;
        }
        if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
          try { audioCtxRef.current.close(); } catch {}
        }
        audioCtxRef.current = null;

        if (recordCancelled) {
          setRecordCancelled(false);
          return;
        }

        const fmt = mimeToFormat(mimeTypeRef.current);
        const blob = new Blob(audioChunksRef.current, { type: mimeTypeRef.current || 'audio/webm' });
        if (blob.size < 1000) {
          Toast.show({ content: '录音时间太短' });
          return;
        }

        Toast.show({ content: '语音识别中...', icon: 'loading' });
        try {
          const fd = new FormData();
          fd.append('audio_file', blob, `recording.${fmt}`);
          fd.append('format', fmt);
          fd.append('sample_rate', '16000');
          const data: any = await api.post('/api/search/asr/recognize', fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 30000,
          });
          Toast.clear();
          const text = data?.data?.text || data?.text || '';
          if (text.trim()) {
            // [Bug-433] 语音入口在调用 handleSend 之前先把 lastMsgTimeRef 推到当前时间，
            // 避免异步识别回调里的 React state 闭包是录音开始时的旧版本，导致会话首句
            // 被错误命中"空闲超时清空"逻辑抹掉。同时 source='voice' 透传到后端便于审计。
            lastMsgTimeRef.current = Date.now();
            handleSend(text.trim(), 'voice');
          } else {
            Toast.show({ content: '未识别到语音内容，请重试' });
          }
        } catch {
          Toast.clear();
          Toast.show({ content: '语音识别失败，请重试' });
        }
      };

      recorder.start(250);
      setRecording(true);
      setRecordCancelled(false);
    } catch {
      Toast.show({ content: '无法访问麦克风，请检查权限设置' });
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setRecording(false);
  };

  const cancelRecording = () => {
    setRecordCancelled(true);
    stopRecording();
    Toast.show({ content: '已取消' });
  };

  const handleRecordTouchStart = (e: React.TouchEvent) => {
    setRecordStartY(e.touches[0].clientY);
    startRecording();
  };

  const handleRecordTouchMove = (e: React.TouchEvent) => {
    const dy = recordStartY - e.touches[0].clientY;
    if (dy > 80) {
      setRecordCancelled(true);
    } else {
      setRecordCancelled(false);
    }
  };

  const handleRecordTouchEnd = () => {
    if (recordCancelled) {
      cancelRecording();
    } else {
      stopRecording();
    }
  };

  const stopTts = useCallback(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (ttsAudioRef.current) {
      ttsAudioRef.current.pause();
      ttsAudioRef.current = null;
    }
    setTtsPlaying(false);
  }, []);

  const handleTTS = useCallback(async (text: string) => {
    if (ttsPlaying) {
      stopTts();
      return;
    }
    stopTts();

    const plainText = text.replace(/\*\*(.*?)\*\*/g, '$1').replace(/---disclaimer---[\s\S]*/g, '').trim();
    if (!plainText) return;

    setTtsPlaying(true);

    try {
      const configRes: any = await api.get('/api/settings/tts-config', { params: { platform: 'h5' } }).catch(() => null);
      const config = configRes?.data || configRes;
      const useCloudTts = config?.tts_provider === 'cloud' || config?.use_cloud_tts;

      if (useCloudTts) {
        const ttsRes: any = await api.post('/api/tts/synthesize', { text: plainText });
        const data = ttsRes.data || ttsRes;
        if (data.audio_url) {
          const audio = new Audio(data.audio_url);
          ttsAudioRef.current = audio;
          audio.onended = () => setTtsPlaying(false);
          audio.onerror = () => {
            setTtsPlaying(false);
            Toast.show({ content: '播放失败，请重试' });
          };
          audio.play();
          return;
        }
      }
    } catch {}

    if (typeof window !== 'undefined' && window.speechSynthesis) {
      const utterance = new SpeechSynthesisUtterance(plainText);
      utterance.lang = 'zh-CN';
      utterance.rate = 1.0;
      utterance.onend = () => setTtsPlaying(false);
      utterance.onerror = () => {
        setTtsPlaying(false);
        tryCloudTtsFallback(plainText);
      };
      window.speechSynthesis.speak(utterance);
    } else {
      tryCloudTtsFallback(plainText);
    }
  }, [ttsPlaying, stopTts]);

  const tryCloudTtsFallback = async (text: string) => {
    try {
      const ttsRes: any = await api.post('/api/tts/synthesize', { text });
      const data = ttsRes.data || ttsRes;
      if (data.audio_url) {
        const audio = new Audio(data.audio_url);
        ttsAudioRef.current = audio;
        audio.onended = () => setTtsPlaying(false);
        audio.onerror = () => {
          setTtsPlaying(false);
          Toast.show({ content: '当前浏览器不支持语音播报' });
        };
        audio.play();
        return;
      }
    } catch {}
    setTtsPlaying(false);
    Toast.show({ content: '当前浏览器不支持语音播报' });
  };

  const handleCopy = (text: string) => {
    navigator.clipboard?.writeText(text).then(() => {
      Toast.show({ content: '已复制', icon: 'success' });
    }).catch(() => {
      Toast.show({ content: '复制失败' });
    });
  };

  const handleNewConversation = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setLastMsgTime(0);
    abortRef.current?.abort();
  }, []);

  // [PRD-420 F5] 切换咨询对象后的会话处理
  // 总策略：自动新建会话 + 用户体验增强（含 5 秒「返回上一会话」撤销栈）
  const handleConsultantSelect = useCallback(async (member: FamilyMemberItem | null) => {
    // 静默打断当前流式响应
    abortRef.current?.abort();

    const prevSessionId = sessionId;
    const prevConsultant = selectedConsultant;
    const prevMessages = messages;
    const targetName = member ? member.nickname : '本人';
    const relationLabel = member
      ? (member.relation_type_name || member.relationship_type || '家庭成员')
      : '本人';
    const displayLabel = member ? `${relationLabel} · ${targetName}` : '本人';

    // [PRD-423 T-08 EVT-02] 切换咨询对象埋点
    const fromTarget: AiChatTargetType = prevConsultant ? 'family' : 'self';
    const toTarget: AiChatTargetType = member ? 'family' : 'self';
    aiChatTrack.targetSwitch(fromTarget, toTarget, {
      from_name: prevConsultant ? prevConsultant.nickname : '本人',
      to_name: targetName,
    });

    // 立即更新选中咨询对象
    setSelectedConsultant(member);

    const hasMessages = prevMessages.length > 0;
    if (!hasMessages) {
      // F5-1：当前会话尚未发出过任何消息（空会话）→ 直接复用，不弹 Toast、不新建
      // 仅把当前会话归属人切换为新选定的对象（若已有 sessionId 则调用 switch-member 接口）
      if (prevSessionId) {
        try {
          await api.post(`/api/chat/sessions/${prevSessionId}/switch-member`, {
            family_member_id: member ? member.id : null,
          });
        } catch {
          // 静默吞掉失败：因为还没消息，下一次发送会自动按新选的对象创建会话
        }
      }
      return;
    }

    // F5-2：非空会话 → 自动新建会话归属新对象
    // [PRD-423 T-08 EVT-03] 归档原会话埋点（实际归档动作由后端在新会话创建时自动处理；前端记录原会话信息）
    if (prevSessionId) {
      aiChatTrack.archiveHistory(prevSessionId, prevMessages.length);
    }

    setMessages([]);
    setSessionId(null);
    setLastMsgTime(0);

    const res = await createChatSession({
      session_type: 'health_qa',
      family_member_id: member ? member.id : undefined,
    });
    if (res.ok && res.sessionId) {
      setSessionId(res.sessionId);
    }

    // F5-2：弹出 Toast + 「返回上一会话」轻按钮（5 秒）
    const expiresAt = Date.now() + 5000;
    setUndoSnapshot({
      sessionId: prevSessionId,
      consultant: prevConsultant,
      messages: prevMessages,
      expiresAt,
    });
    // [PRD-423 T-05] 切换提示横条文案严格对齐 PRD §5
    setUndoToastText(`已切换为 ${displayLabel} 咨询，已为您开启新对话`);
    setUndoToastVisible(true);
    if (undoTimerRef.current) clearTimeout(undoTimerRef.current);
    undoTimerRef.current = setTimeout(() => {
      setUndoToastVisible(false);
      setUndoSnapshot(null);
    }, 5000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, selectedConsultant, messages]);

  // [PRD-420 F5-2] 「返回上一会话」按钮点击：恢复原会话与原咨询对象
  const handleUndoSwitch = useCallback(() => {
    if (!undoSnapshot || Date.now() > undoSnapshot.expiresAt) return;
    setSessionId(undoSnapshot.sessionId);
    setSelectedConsultant(undoSnapshot.consultant);
    setMessages(undoSnapshot.messages);
    setUndoToastVisible(false);
    setUndoSnapshot(null);
    if (undoTimerRef.current) {
      clearTimeout(undoTimerRef.current);
      undoTimerRef.current = null;
    }
  }, [undoSnapshot]);

  // [PRD-420 F6] 进入页面默认咨询对象为「本人」（不读取上次选择，不与菜单模式联动）
  useEffect(() => {
    setSelectedConsultant(null);
    return () => {
      if (undoTimerRef.current) {
        clearTimeout(undoTimerRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // [PRD-423 T-08 EVT-01] 进入对话页埋点（仅触发一次）
  const pageViewSentRef = useRef(false);
  useEffect(() => {
    if (pageViewSentRef.current) return;
    pageViewSentRef.current = true;
    aiChatTrack.pageView('self');
  }, []);

  // [PRD-423 T-03] 冷启动「无本人档案」检测：fallback 到「未选择档案」并展示轻提示
  // 规则：进入页面后拉取家庭成员，若不存在 is_self=true 的档案 → 显示提示
  const [showNoSelfTip, setShowNoSelfTip] = useState(false);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res: any = await api.get('/api/family/members');
        const data = res?.data || res;
        const list: any[] = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
        const hasSelf = list.some((m) => !!m?.is_self);
        if (!cancelled && !hasSelf) {
          setShowNoSelfTip(true);
        }
      } catch {
        // 静默失败：不影响主流程
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // [PRD-423 T-08 EVT-09] 「先完善本人档案」轻提示点击
  const handleNoSelfTipClick = useCallback(() => {
    aiChatTrack.noSelfProfileTipClick();
    router.push('/health-archive?target=self&from=ai-chat');
  }, [router]);

  const handleSelectSession = useCallback(async (sid: string) => {
    setMessages([]);
    setSessionId(sid);
    setSidebarOpen(false);
    await loadSessionMessages(sid);
  }, []);

  const hasConversation = messages.length > 0;

  // v1.0 全局开关取并集
  // [Bug-419 H-5 2026-05-08] 全部使用安全字段读取（?. + ??），即使后端返回的
  // 配置缺失子字段，也不会触发 "Cannot read properties of undefined" → 保护首页
  // 不会因任何字段读取异常而整片塌陷。
  const sw = aiHomeConfig.global_switches || FALLBACK_CONFIG.global_switches;
  const welcomeVisible = sw?.welcome_visible ?? true;
  const healthTipsVisible = (sw?.health_tips_visible ?? true) && (aiHomeConfig.health_tips?.visible ?? true);
  const funcGridVisible = (sw?.func_grid_visible ?? true) && (aiHomeConfig.func_grid?.visible ?? true);
  const recommendedVisible = sw?.recommended_visible ?? true;
  const emptyPlaceholderVisible = sw?.empty_placeholder_visible ?? true;
  const familyPillVisible = (sw?.family_pill_visible ?? true) && (aiHomeConfig.input?.family_consult?.enabled ?? true);
  const archiveLinkVisible = (sw?.archive_link_visible ?? true) && (aiHomeConfig.input?.family_consult?.show_archive_link ?? true);
  const voiceInputVisible = (sw?.voice_input_visible ?? true) && (aiHomeConfig.input?.enable_voice ?? true);
  const floatingButtonVisible = (sw?.floating_button_visible ?? true) && (aiHomeConfig.floating_button?.enabled ?? true);

  // 主标题占位符替换（[Bug-419 H-5] 全部 ?. + 默认值兜底）
  const renderMainTitle = (): string => {
    const tpl = aiHomeConfig.welcome?.main_title || '早上好，{昵称}！';
    const nick = (aiHomeConfig.welcome?.show_nickname && user?.nickname) ? user.nickname : '';
    return tpl.replace('{昵称}', nick || '朋友');
  };
  const renderFamilyPillText = (): string => {
    const tpl = aiHomeConfig.input?.family_consult?.template || '为({name})咨询';
    // [PRD-420 F1] 按钮文案随当前咨询对象动态变化：本人 / 儿子·苏俊林 / 老婆·朱
    let name = '本人';
    if (selectedConsultant) {
      const rel = selectedConsultant.relation_type_name || selectedConsultant.relationship_type;
      name = rel ? `${rel}·${selectedConsultant.nickname}` : selectedConsultant.nickname;
    }
    return tpl.replace('{name}', name);
  };

  // 兜底功能宫格项：优先使用配置中的 items；若为空，使用 FALLBACK 3 项
  const configuredItems = (aiHomeConfig.func_grid?.items && aiHomeConfig.func_grid.items.length > 0)
    ? aiHomeConfig.func_grid.items
    : FALLBACK_CONFIG.func_grid.items;
  const gridItems = (configuredItems || [])
    .filter((g) => g && g.enabled)
    .slice(0, aiHomeConfig.func_grid?.max_count || 6);

  // [Bug-419 H-5] 顶栏字段安全读取，缺失时按 v1.0 设计图（无顶栏）兜底
  // [PRD-425] 旧逻辑保留但前端忽略（新版顶栏强制显示，不再受 topbar.visible 控制）
  const topbarShowSidebar = aiHomeConfig.topbar?.show_sidebar ?? true;
  const topbarShowMoreMenu = aiHomeConfig.topbar?.show_more_menu ?? true;

  // [PRD-425] 新版顶栏标题：取 ai_chat.signature；为空 / 接口异常 → 兜底"小康"
  // 文案截断：超过 8 个汉字加省略号
  const rawSignature = aiHomeConfig.ai_chat?.signature || '';
  const topbarTitle = (() => {
    const s = (rawSignature && rawSignature.trim()) ? rawSignature.trim() : '小康';
    return s.length > 8 ? s.slice(0, 8) + '…' : s;
  })();

  // [PRD-425] 徽标展示形态：null=不显示；0=小红点；1~99=数字；>=100="99+"
  const renderUnreadBadge = () => {
    if (unreadCount === null) return null;
    const isDot = unreadCount === 0;
    const display = unreadCount >= 100 ? '99+' : String(unreadCount);
    return (
      <span
        onClick={(e) => {
          e.stopPropagation();
          // 点击徽标 → 跳转通知中心（不自动清零）
          router.push('/messages');
        }}
        style={{
          position: 'absolute',
          top: -6,
          right: -14,
          minWidth: isDot ? 8 : 16,
          height: isDot ? 8 : 16,
          padding: isDot ? 0 : '0 4px',
          borderRadius: 9,
          background: '#FF3B30',
          color: '#fff',
          fontSize: 10,
          fontWeight: 600,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          lineHeight: 1,
          boxShadow: '0 0 0 1.5px #fff',
          cursor: 'pointer',
        }}
        data-testid="ai-home-unread-badge"
        aria-label={isDot ? '有新通知' : `${display} 条未读通知`}
      >
        {!isDot && display}
      </span>
    );
  };

  return (
    <div
      className="flex flex-col h-screen"
      style={{
        background: THEME.background,
        maxWidth: 750,
        margin: '0 auto',
        overflow: 'hidden', /* [Bug-431] 禁止整页滚动/橡皮筋回弹，避免顶部栏被"顶出去一截" */
        overscrollBehavior: 'none' as any,
      }}
    >
      {/* [Bug-431 2026-05-08] 顶部"小康"栏彻底独立钉死：
          - position: fixed（脱离 flex 文档流，不与下方消息列表共享任何滚动容器）
          - 内部布局改为绝对定位三元素（左 ☰ / 中 小康标题 / 右 ⋯）：栏内元素位置固定不依赖 flex 重新计算，避免交互瞬间抖动
          - 不允许任何 transition / animation / transform：栏自身像石头一样钉死
          - 用 sentinel <div> 占位 48px 高度，保证下方内容不被 fixed 顶栏遮挡（同时取代原 sticky 占位行为） */}
      <SectionErrorBoundary name="topbar">
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 100,
            height: 'calc(48px + env(safe-area-inset-top))',
            paddingTop: 'env(safe-area-inset-top)',
            background: THEME.cardBg,
            maxWidth: 750,
            marginLeft: 'auto',
            marginRight: 'auto',
            transition: 'none',
            transform: 'none',
            willChange: 'auto',
          }}
          data-testid="ai-home-topbar"
        >
          {/* 内层 48px 工作区，使用绝对定位钉死三个子元素位置 */}
          <div style={{ position: 'relative', height: 48, width: '100%' }}>
            {/* 左：☰ 汉堡菜单（绝对定位 left:8） */}
            {topbarShowSidebar ? (
              <button
                className="flex items-center justify-center"
                style={{
                  position: 'absolute',
                  left: 8,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: 32,
                  height: 32,
                  fontSize: 22,
                  color: THEME.textPrimary,
                  background: 'transparent',
                  border: 'none',
                  padding: 0,
                  margin: 0,
                  lineHeight: 1,
                }}
                onClick={() => setSidebarOpen(true)}
                aria-label="历史会话"
              >
                ☰
              </button>
            ) : null}

            {/* [PRD-439 F-01] "小康"标题：整体靠左，与左侧 ☰ 按钮间距 8px
                ☰ 按钮在 left:8 + 宽 32px，紧邻其右 = left:48；再加 8px 间距 = left:56 - 即原 56，
                这里的关键是把 justifyContent 从 flex-start 保持为左对齐，且容器 left 改为 48 + 间距 8 = 56 不动，
                但去掉 right: 56 让标题尽量左侧。 */}
            <div
              style={{
                position: 'absolute',
                left: 48, /* ☰ 按钮右侧紧邻 */
                right: 56,
                top: 0,
                bottom: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
                paddingLeft: 8, /* [PRD-439 F-01] ☰ 与"小康"间距 8px */
                minWidth: 0,
              }}
            >
              <span
                className="relative inline-block"
                style={{
                  fontSize: 17,
                  fontWeight: 600,
                  color: THEME.textPrimary,
                  lineHeight: '24px',
                  cursor: 'default',
                  whiteSpace: 'nowrap',
                  overflow: 'visible',
                }}
                data-testid="ai-home-topbar-title"
              >
                {topbarTitle}
                {renderUnreadBadge()}
              </span>
            </div>

            {/* 右：⋯ 更多菜单（绝对定位 right:8） */}
            {topbarShowMoreMenu ? (
              <button
                className="flex items-center justify-center tracking-widest"
                style={{
                  position: 'absolute',
                  right: 8,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: 32,
                  height: 32,
                  fontSize: 22,
                  color: THEME.textPrimary,
                  background: 'transparent',
                  border: 'none',
                  padding: 0,
                  margin: 0,
                  lineHeight: 1,
                }}
                onClick={() => setMoreMenuOpen(true)}
                aria-label="更多菜单"
              >
                ⋯
              </button>
            ) : null}
          </div>
        </div>
      </SectionErrorBoundary>

      {/* [Bug-431] 顶栏占位：补偿 fixed 顶栏占用的视觉高度，保证下方内容不被遮挡 */}
      <div
        aria-hidden
        style={{
          flexShrink: 0,
          height: 'calc(48px + env(safe-area-inset-top))',
        }}
      />

      {/* Main Content */}
      {/* [Bug-419 H-4/H-7 2026-05-08] 各区块独立 ErrorBoundary，任何子组件
          异常仅降级该区块（默认占位 8px），绝不让顶部菜单/输入框/浮动按钮
          被牵连 unmount，杜绝"422 → 整页白屏"事故。 */}
      {/* 顶部欢迎面板 + 消息列表共享同一个滚动容器，整体瀑布流：
          欢迎区/健康贴士/功能宫格/推荐问 始终在文档流顶部，向下连接消息列表，
          滚动时菜单栏会被自然推出视野，不再有折叠/悬浮圆按钮交互。 */}
      <div
        ref={messageScrollRef}
        className="flex-1 overflow-y-auto relative"
      >
        {/* 顶部欢迎面板：常驻文档流顶部，跟随主滚动容器一起滚动 */}
        <div
          data-testid="ai-home-top-panel"
          style={{
            background: THEME.background,
          }}
        >
          <div className="px-4 py-3">
            {/* v1.0 欢迎区：左头像 + 右文字 横向布局 */}
            <SectionErrorBoundary name="welcome">
              {welcomeVisible && (
                <div className="flex items-center gap-3 py-4">
                  {aiHomeConfig.welcome?.avatar?.type === 'image' && aiHomeConfig.welcome?.avatar?.image_url ? (
                    <img
                      src={aiHomeConfig.welcome.avatar.image_url}
                      alt="avatar"
                      className="rounded-full flex-shrink-0"
                      style={{ width: 56, height: 56, objectFit: 'cover' }}
                    />
                  ) : (
                    <div
                      className="flex items-center justify-center rounded-full text-3xl flex-shrink-0"
                      style={{ width: 56, height: 56, background: THEME.gradient, color: '#fff' }}
                    >
                      {aiHomeConfig.welcome?.avatar?.emoji || '🌿'}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-lg font-bold truncate" style={{ color: THEME.textPrimary }}>
                      {renderMainTitle()}
                    </div>
                    <div className="text-sm mt-0.5 truncate" style={{ color: THEME.textSecondary }}>
                      {aiHomeConfig.welcome?.sub_title || pickedSubtitle || '我是您的AI健康顾问小康'}
                    </div>
                  </div>
                </div>
              )}
            </SectionErrorBoundary>

            {/* v1.0 紫色今日健康贴士轮播卡（图片做整张卡片背景） */}
            <SectionErrorBoundary name="health_tips">
              {healthTipsVisible && banners.length > 0 && (
                <div className="rounded-2xl overflow-hidden mb-4 shadow-lg" style={{ background: 'linear-gradient(135deg, #5B6CFF 0%, #8B5CF6 100%)' }}>
                  <Swiper
                    autoplay
                    autoplayInterval={(aiHomeConfig.health_tips?.interval_seconds || 4) * 1000}
                    loop
                    indicator={(aiHomeConfig.health_tips?.show_indicator ?? true) ? undefined : () => null}
                  >
                    {banners.map(banner => (
                      <Swiper.Item key={banner.id}>
                        <div
                          className="bg-cover bg-center cursor-pointer"
                          style={{
                            height: 130,
                            backgroundImage: `url(${banner.image_url})`,
                            backgroundColor: '#5B6CFF',
                          }}
                          onClick={() => banner.link_url && router.push(banner.link_url)}
                        />
                      </Swiper.Item>
                    ))}
                  </Swiper>
                </div>
              )}
            </SectionErrorBoundary>

            {/* v1.0 功能宫格 7 字段 */}
            <SectionErrorBoundary name="func_grid">
              {funcGridVisible && gridItems.length > 0 && (
                <div
                  className={`grid gap-3 mb-4`}
                  style={{ gridTemplateColumns: `repeat(${aiHomeConfig.func_grid?.columns || 3}, minmax(0, 1fr))` }}
                >
                  {gridItems.map(it => (
                    <div
                      key={it.id}
                      className="relative flex flex-col items-center justify-center gap-1.5 py-4 rounded-2xl cursor-pointer active:opacity-80"
                      style={{
                        background: `linear-gradient(135deg, ${it.gradient_start} 0%, ${it.gradient_end} 100%)`,
                        color: '#fff',
                        minHeight: 90,
                      }}
                      onClick={() => {
                        const p = it.target_path;
                        if (p && (p.startsWith('/') || p.startsWith('http'))) {
                          if (p.startsWith('http')) window.location.href = p;
                          else router.push(p);
                        }
                      }}
                    >
                      <span className="text-2xl">{it.icon || '📌'}</span>
                      <span className="text-sm font-semibold">{it.main_text}</span>
                      <span className="text-xs opacity-90 text-center px-1">{it.sub_text}</span>
                      {it.badge && (
                        <span
                          className="absolute top-1 right-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold"
                          style={{ background: '#FF4D4F', color: '#fff' }}
                        >
                          {it.badge}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </SectionErrorBoundary>

            {/* v1.0 推荐问横向滚动胶囊（位于功能宫格下方、空对话占位上方） */}
            <SectionErrorBoundary name="recommended">
              {recommendedVisible && recommendQuestions.length > 0 && (
                <div className="mb-4">
                  <div
                    className="flex gap-2 overflow-x-auto pb-2"
                    style={{ scrollbarWidth: 'none' as any, msOverflowStyle: 'none' as any }}
                  >
                    {recommendQuestions.map((q, i) => (
                      <div
                        key={i}
                        className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-full cursor-pointer active:opacity-70"
                        style={{ background: '#fff', border: `1px solid ${THEME.divider}`, whiteSpace: 'nowrap' }}
                        onClick={() => {
                          // [Bug-428] 推荐胶囊点击：自动以胶囊文本作为用户消息发送
                          // [Bug-433] 同步 lastMsgTimeRef 并标注 source='preset'，避免会话首句被
                          // 错误命中的"空闲超时清空"逻辑抹掉，且便于后端审计预设按钮入口。
                          lastMsgTimeRef.current = Date.now();
                          handleSend(q.text, 'preset');
                        }}
                      >
                        {q.tag && <span className="text-base">{q.tag}</span>}
                        <span className="text-sm" style={{ color: THEME.textPrimary }}>{q.text.length > 12 ? q.text.slice(0, 12) + '…' : q.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </SectionErrorBoundary>

            {/* v1.0 空对话占位（大图标 + 主标题 居中） */}
            <SectionErrorBoundary name="empty_placeholder">
              {emptyPlaceholderVisible && messages.length === 0 && (
                <div className="flex flex-col items-center py-8">
                  <div className="text-5xl mb-3 opacity-60">{aiHomeConfig.empty_placeholder?.icon || '💬'}</div>
                  <div className="text-base" style={{ color: THEME.textSecondary }}>
                    {aiHomeConfig.empty_placeholder?.main_title || '还没有对话记录'}
                  </div>
                </div>
              )}
            </SectionErrorBoundary>
          </div>
        </div>

        {/* 消息列表：紧接在顶部欢迎面板之后，二者同处一个滚动容器，
            形成"菜单栏 → 消息流"的自然瀑布流排布。 */}
        {hasConversation && (
          /* [PRD-429] AI 回答消息满屏排版改造：去气泡纯文本流，
             用户消息和 AI 回答均无 background/border/borderRadius，
             头像独占一行放在文字上方，左右各 12px 安全边距，整体 max-width 760px 居中（PC/折叠屏） */
          <div
            data-testid="ai-home-message-flow"
            style={{
              padding: '12px 12px',
              maxWidth: 760,
              margin: '0 auto',
              width: '100%',
            }}
          >
            {messages.map((msg, idx) => {
              const prevTime = idx > 0 ? messages[idx - 1].time : null;
              const showTime = shouldShowTime(prevTime, msg.time);
              const isUser = msg.role === 'user';
              // [PRD-433 F-06] 操作按钮行：所有非流式 AI 消息都显示（不仅 lastAiMsg）
              const showAiActions = !isUser && !msg.isStreaming;
              const senderName = '小康';
              const disclaimerText = 'AI 生成内容仅供参考，不作为诊断依据';
              const hasReferences = !isUser && Array.isArray(msg.references) && msg.references.length > 0;

              if (isUser) {
                // [PRD-433 F-01 + F-04] 用户消息：右侧浅蓝气泡，无头像
                return (
                  <div key={msg.id} style={{ marginBottom: 24 }} data-testid="ai-home-user-message">
                    {showTime && (
                      <div className="text-center" style={{ padding: '8px 0' }} data-testid="ai-home-time-divider">
                        <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                          {formatWeChatTime(msg.time)}
                        </span>
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginRight: 16 }}>
                      <div
                        data-testid="ai-home-user-bubble"
                        style={{
                          background: '#E6F0FF',
                          color: '#1F2937',
                          borderRadius: 14,
                          padding: '10px 14px',
                          maxWidth: 'min(75vw, 540px)',
                          fontSize: 16,
                          lineHeight: 1.5,
                          wordBreak: 'break-word',
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {msg.content}
                      </div>
                    </div>
                  </div>
                );
              }

              // [PRD-433 F-02/F-03/F-06/F-08/F-10/F-13/F-14] AI 消息：白底卡片
              return (
                <div key={msg.id} style={{ marginBottom: 24 }} data-testid="ai-home-ai-message">
                  {showTime && (
                    <div className="text-center" style={{ padding: '8px 0' }} data-testid="ai-home-time-divider">
                      <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                        {formatWeChatTime(msg.time)}
                      </span>
                    </div>
                  )}
                  {/* [PRD-432 / PRD-439 F-03] AI 回答顶部「咨询对象档案」折叠胶囊：
                      仅在已选定咨询对象时显示（未选则隐藏，避免空胶囊） */}
                  {((msg.consultantTargetId ?? selectedConsultant?.id ?? 0) > 0) && (
                  <div data-testid="ai-home-profile-card-wrapper" style={{ marginBottom: 8 }}>
                    <ProfileCard
                      consultantId={(msg.consultantTargetId ?? selectedConsultant?.id ?? 0) as number}
                      onGoComplete={(cid) => router.push(`/health-archive?target=${cid}&from=ai-chat`)}
                      onGoMedicationManage={(cid, autoCreate) =>
                        router.push(`/health-plan/medications?target=${cid}${autoCreate ? '&action=create' : ''}`)
                      }
                    />
                  </div>
                  )}
                  {/* [PRD-433 F-03] AI 头像 + 名称行：保留在卡片外部上方，去掉「· 健康助手」 */}
                  <div className="flex items-center" style={{ marginBottom: 6, paddingLeft: 16 }}>
                    <div
                      className="flex-shrink-0 flex items-center justify-center rounded-full"
                      style={{ width: 28, height: 28, background: THEME.gradient, color: '#fff', fontSize: 14 }}
                    >
                      🌿
                    </div>
                    <span style={{ marginLeft: 8, fontSize: 14, color: '#666' }}>{senderName}</span>
                  </div>
                  {/* [PRD-433 F-02] AI 卡片：白底 + 浅灰描边，左右屏幕边距 16px */}
                  <div
                    data-testid="ai-home-ai-card"
                    style={{
                      background: '#FFFFFF',
                      border: '1px solid #EAEBED',
                      borderRadius: 12,
                      padding: '14px 16px',
                      marginLeft: 16,
                      marginRight: 16,
                    }}
                  >
                    {/* 正文 */}
                    <div
                      className="ai-fullwidth-message"
                      style={{
                        fontSize: 16,
                        lineHeight: 1.6,
                        color: THEME.textPrimary,
                        wordBreak: 'break-word',
                        overflowWrap: 'break-word',
                      }}
                    >
                      <span dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
                      {/* [PRD-433 F-10] 流式输出已去除光标闪烁 span */}
                    </div>

                    {/* [PRD-433 F-14] 参考资料（容错：仅在数组非空时渲染） */}
                    {hasReferences && (
                      <div
                        data-testid="ai-home-ai-references"
                        style={{
                          marginTop: 12,
                          paddingTop: 10,
                          borderTop: '1px dashed #EAEBED',
                          fontSize: 12,
                          color: '#6B7280',
                        }}
                      >
                        <div style={{ marginBottom: 4, fontWeight: 500 }}>参考资料</div>
                        {msg.references!.map((ref, i) => (
                          <div key={i} style={{ marginTop: 2, lineHeight: 1.5 }}>
                            {ref.url ? (
                              <a
                                href={ref.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ color: '#1677FF', textDecoration: 'none', wordBreak: 'break-all' }}
                              >
                                [{i + 1}] {ref.title}
                              </a>
                            ) : (
                              <span style={{ color: '#6B7280' }}>[{i + 1}] {ref.title}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* [PRD-433 F-08] 免责声明：每条 AI 卡片底部都显示，操作按钮行上方 */}
                    {!msg.isStreaming && (
                      <div
                        data-testid="ai-home-ai-disclaimer"
                        style={{
                          marginTop: 12,
                          fontSize: 12,
                          color: '#9CA3AF',
                          lineHeight: 1.4,
                        }}
                      >
                        {disclaimerText}
                      </div>
                    )}

                    {/* [PRD-433 F-06] 操作按钮行：所有非流式 AI 消息都显示，朗读按钮放最右 */}
                    {showAiActions && (
                      <div
                        data-testid="ai-home-ai-action-bar"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          marginTop: 10,
                          paddingTop: 8,
                          borderTop: '1px solid #F2F3F5',
                          gap: 24,
                        }}
                      >
                        <button
                          aria-label="复制"
                          onClick={() => handleCopy(msg.content)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            minWidth: 44,
                            minHeight: 44,
                            padding: '0 4px',
                            background: 'transparent',
                            border: 'none',
                            color: '#6B7280',
                            fontSize: 13,
                            cursor: 'pointer',
                            gap: 4,
                          }}
                        >
                          <span style={{ fontSize: 20, lineHeight: 1 }}>📋</span>
                          <span>复制</span>
                        </button>
                        <button
                          aria-label="分享"
                          onClick={() => setShareOpen(true)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            minWidth: 44,
                            minHeight: 44,
                            padding: '0 4px',
                            background: 'transparent',
                            border: 'none',
                            color: '#6B7280',
                            fontSize: 13,
                            cursor: 'pointer',
                            gap: 4,
                          }}
                        >
                          <span style={{ fontSize: 20, lineHeight: 1 }}>🔗</span>
                          <span>分享</span>
                        </button>
                        <button
                          aria-label={ttsPlaying ? '停止朗读' : '朗读'}
                          onClick={() => handleTTS(msg.content)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            minWidth: 44,
                            minHeight: 44,
                            padding: '0 4px',
                            marginLeft: 'auto',
                            background: 'transparent',
                            border: 'none',
                            color: ttsPlaying ? THEME.primary : '#6B7280',
                            fontSize: 13,
                            cursor: 'pointer',
                            gap: 4,
                          }}
                        >
                          <span style={{ fontSize: 20, lineHeight: 1 }}>🔁</span>
                          <span>{ttsPlaying ? '停止' : '朗读'}</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            {/* [PRD-433 F-11] Loading 卡片：白底+浅灰描边+88~90% 占屏，外部头像名称行保留 */}
            {sending && !messages.some(m => m.isStreaming) && (
              <div style={{ marginBottom: 24 }} data-testid="ai-home-ai-loading-card">
                <div className="flex items-center" style={{ marginBottom: 6, paddingLeft: 16 }}>
                  <div
                    className="flex-shrink-0 flex items-center justify-center rounded-full"
                    style={{ width: 28, height: 28, background: THEME.gradient, color: '#fff', fontSize: 14 }}
                  >
                    🌿
                  </div>
                  <span style={{ marginLeft: 8, fontSize: 14, color: '#666' }}>小康</span>
                </div>
                <div
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid #EAEBED',
                    borderRadius: 12,
                    padding: '14px 16px',
                    marginLeft: 16,
                    marginRight: 16,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <span style={{ fontSize: 16, color: '#6B7280' }}>小康正在思考中…</span>
                  <span className="flex gap-1" style={{ alignItems: 'center' }}>
                    <span className="w-2 h-2 rounded-full" style={{ background: '#9CA3AF', animation: 'bounce 1.4s infinite ease-in-out both', animationDelay: '0s' }} />
                    <span className="w-2 h-2 rounded-full" style={{ background: '#9CA3AF', animation: 'bounce 1.4s infinite ease-in-out both', animationDelay: '0.2s' }} />
                    <span className="w-2 h-2 rounded-full" style={{ background: '#9CA3AF', animation: 'bounce 1.4s infinite ease-in-out both', animationDelay: '0.4s' }} />
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* [PRD-439 F-02/F-08] 健康打卡入口下线，原位替换为 🔔 提醒铃铛
          - 复用悬浮位置（默认 bottom 120）+ 数字徽标
          - 点击弹出"今日待办"抽屉（用药提醒 + 预约提醒） */}
      <SectionErrorBoundary name="floating_button">
        {floatingButtonVisible && (
          <ReminderBellButton
            badgeCount={reminderBadge}
            defaultBottom={120}
            position={aiHomeConfig.floating_button?.position === 'left_bottom' ? 'left' : 'right'}
            onClick={() => setReminderOpen(true)}
          />
        )}
      </SectionErrorBoundary>
      {/* [PRD-439 F-04~F-06] 今日待办抽屉 */}
      <SectionErrorBoundary name="reminder_drawer">
        <ReminderDrawer
          open={reminderOpen}
          onClose={() => setReminderOpen(false)}
          onChangeBadge={refreshReminderBadge}
          onGoMedicationManage={() => {
            setReminderOpen(false);
            router.push('/medication-plans');
          }}
          onGoOrderList={() => {
            setReminderOpen(false);
            router.push('/unified-orders');
          }}
        />
      </SectionErrorBoundary>

      {/* Bottom Quick Tags (兼容旧版本，仅在 quick_tags.visible 时显示) */}
      {false && !hasConversation && aiHomeConfig.quick_tags?.visible && funcButtons.length > 0 && (
        <div
          className="flex-shrink-0 overflow-x-auto px-4 py-2 flex gap-2"
          style={{ borderTop: `1px solid ${THEME.divider}`, background: THEME.cardBg, scrollbarWidth: 'none' }}
        >
          {funcButtons.slice(0, aiHomeConfig.quick_tags?.max_count || 8).map(btn => (
            <div
              key={btn.id}
              className="flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium cursor-pointer active:opacity-70"
              style={{ background: THEME.primaryLight, color: THEME.primary, whiteSpace: 'nowrap' }}
              onClick={() => handleFuncButton(btn)}
            >
              {btn.name}
            </div>
          ))}
        </div>
      )}

      {/* Input Bar */}
      <div
        className="flex-shrink-0 px-4 py-3"
        style={{
          background: THEME.cardBg,
          borderTop: `1px solid ${THEME.divider}`,
          paddingBottom: 'calc(12px + env(safe-area-inset-bottom))',
        }}
      >
        {/* [PRD-426] 删除输入框上方"+ 选择咨询人"浮层（含其内嵌的 RecommendCards 推荐题），底部"为(XX)咨询 ⇄"作为唯一咨询人切换入口 */}

        {voiceMode && voiceSupported ? (
          <div className="flex items-center gap-3">
            <button
              className="flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-full"
              style={{ background: THEME.primaryLight, color: THEME.primary }}
              onClick={handleMicToggle}
              aria-label="切换为键盘"
            >
              ⌨️
            </button>
            <div
              className="flex-1 flex items-center justify-center rounded-full py-3 select-none"
              style={{
                background: recording ? THEME.primaryLight : THEME.background,
                border: recording ? `2px solid ${THEME.primary}` : `2px solid transparent`,
                transition: 'all 0.2s',
              }}
              onTouchStart={handleRecordTouchStart}
              onTouchMove={handleRecordTouchMove}
              onTouchEnd={handleRecordTouchEnd}
              onMouseDown={() => startRecording()}
              onMouseUp={() => { if (recordCancelled) cancelRecording(); else stopRecording(); }}
            >
              {recording ? (
                <div className="flex items-center gap-2">
                  <div className="flex gap-0.5 items-end h-5">
                    {[0, 1, 2, 3, 4].map(i => (
                      <div
                        key={i}
                        className="w-1 rounded-full transition-all duration-100"
                        style={{
                          background: THEME.primary,
                          height: `${8 + volumeLevel * 12 * (1 + Math.sin(i * 1.2))}px`,
                        }}
                      />
                    ))}
                  </div>
                  <span className="text-sm" style={{ color: recordCancelled ? '#FF4D4F' : THEME.primary }}>
                    {recordCancelled ? '松开取消' : '松开发送'}
                  </span>
                </div>
              ) : (
                <span className="text-sm" style={{ color: THEME.textSecondary }}>按住说话</span>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-end gap-2">
            {voiceSupported && voiceInputVisible && (
              <button
                className="flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-full mb-0"
                style={{ background: THEME.primaryLight, color: THEME.primary }}
                onClick={handleMicToggle}
                aria-label="语音输入"
              >
                🎤
              </button>
            )}
            <div
              className="flex-1 flex items-end px-4 py-2"
              style={{ background: '#F5F7FA', borderRadius: 22, minHeight: 44 }}
            >
              <textarea
                ref={textareaRef}
                className="flex-1 bg-transparent outline-none text-sm resize-none leading-6"
                placeholder={aiHomeConfig.input?.placeholder || '发消息或按住说话...'}
                value={inputValue}
                onChange={handleTextareaInput}
                /* [PRD-426] 已移除 onFocus/onBlur 监听：原用于"+ 选择咨询人"浮层显隐控制 */
                /* [Bug-431] 已彻底移除聚焦时自动收起：欢迎面板的唯一收起触发器 = 用户主动点击发送按钮（见 handleSend） */
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                rows={1}
                style={{ color: THEME.textPrimary, maxHeight: 120, height: 24 }}
              />
            </div>
            {/* v1.0 丁香派智能隐藏：键盘模式 + 输入框为空 → 灰显；有文字 → 亮起 */}
            {/* [PRD-433 F-12] 发送按钮配色与浅蓝气泡协调（活跃态 #1677FF） */}
            <button
              className="flex-shrink-0 flex items-center justify-center rounded-full text-sm font-medium mb-0"
              style={{
                width: 44,
                height: 44,
                background: inputValue.trim() ? '#1677FF' : '#D1D5DB',
                color: '#fff',
                transition: 'background 0.2s',
                opacity: inputValue.trim() ? 1 : 0.6,
                cursor: inputValue.trim() ? 'pointer' : 'not-allowed',
              }}
              onClick={() => handleSend()}
              disabled={!inputValue.trim() || sending}
              aria-label="发送"
            >
              ➤
            </button>
          </div>
        )}

        {/* v1.0 第二层：家庭成员快捷栏（家庭成员咨询胶囊 + 查看档案） */}
        {!voiceMode && (familyPillVisible || archiveLinkVisible) && (
          <div className="flex items-center justify-between gap-3 mt-2">
            {familyPillVisible ? (
              <button
                className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-full"
                style={{ background: THEME.primaryLight, color: THEME.primary, fontSize: 12 }}
                onClick={() => setConsultantOpen(true)}
                aria-label="切换咨询对象"
              >
                <span>{renderFamilyPillText()}</span>
                <span style={{ fontSize: 10 }}>⇆</span>
              </button>
            ) : <div />}
            {archiveLinkVisible && (
              <button
                className="flex-shrink-0 text-xs"
                style={{ color: THEME.textSecondary }}
                onClick={() => {
                  const p = aiHomeConfig.input?.family_consult?.archive_path || '/health-records';
                  if (p.startsWith('/')) router.push(p);
                }}
                aria-label="查看档案"
              >
                查看档案 ›
              </button>
            )}
          </div>
        )}
      </div>

      {/* Overlays */}
      <Sidebar
        visible={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewConversation={handleNewConversation}
      />
      <MoreMenu
        visible={moreMenuOpen}
        onClose={() => setMoreMenuOpen(false)}
        onShare={() => setShareOpen(true)}
      />
      <ConsultTargetPicker
        visible={consultantOpen}
        onClose={() => setConsultantOpen(false)}
        currentMemberId={selectedConsultant ? selectedConsultant.id : null}
        onSelect={(m) => {
          setConsultantOpen(false);
          handleConsultantSelect(m);
        }}
      />
      <SharePanel visible={shareOpen} onClose={() => setShareOpen(false)} />

      {/* [PRD-423 T-03] 冷启动「无本人档案」轻提示横条 */}
      {showNoSelfTip && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 999,
            height: 36,
            background: '#EAF4FF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 12px',
            fontSize: 13,
            color: '#2E2E2E',
            cursor: 'pointer',
          }}
          onClick={handleNoSelfTipClick}
          data-testid="no-self-profile-tip"
        >
          <span style={{ marginRight: 4 }}>建议先完善本人档案，让小康给您更精准的建议</span>
          <span style={{ color: '#1677FF', fontWeight: 500 }}>→</span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowNoSelfTip(false);
            }}
            style={{
              position: 'absolute',
              right: 8,
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'transparent',
              border: 'none',
              fontSize: 16,
              color: '#999',
              cursor: 'pointer',
              padding: 4,
            }}
            aria-label="关闭"
          >
            ×
          </button>
        </div>
      )}

      {/* [PRD-420 F5-2 + PRD-423 T-05] 切换会话提示横条（PRD §5：高度 36px / 底色 #EAF4FF / 文字 13px / 主文本色 #2E2E2E） */}
      {undoToastVisible && undoSnapshot && (
        <div
          style={{
            position: 'fixed',
            top: 48,
            left: 0,
            right: 0,
            zIndex: 1000,
            height: 36,
            background: '#EAF4FF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 12px',
            fontSize: 13,
            color: '#2E2E2E',
            transition: 'opacity 200ms ease-out',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          }}
          data-testid="consult-switch-toast"
        >
          <span style={{ fontSize: 13, lineHeight: 1.4, color: '#2E2E2E', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{undoToastText}</span>
          <button
            onClick={handleUndoSwitch}
            style={{
              background: 'transparent',
              color: '#1677FF',
              border: '1px solid #1677FF',
              borderRadius: 16,
              padding: '2px 10px',
              fontSize: 12,
              cursor: 'pointer',
              flexShrink: 0,
              marginLeft: 8,
            }}
            data-testid="consult-switch-undo-btn"
          >
            返回上一会话
          </button>
        </div>
      )}

      <style jsx global>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1); }
        }
        /* [PRD-429] AI 满屏排版：代码块/表格/图片/卡片自适应规则 */
        .ai-fullwidth-message pre {
          background: #F5F7FA;
          border-radius: 8px;
          padding: 12px 16px;
          overflow-x: auto;
          font-size: 13px;
          line-height: 1.5;
          margin: 8px 0;
        }
        .ai-fullwidth-message code {
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }
        .ai-fullwidth-message table {
          display: block;
          overflow-x: auto;
          max-width: 100%;
          border-collapse: collapse;
          margin: 8px 0;
        }
        .ai-fullwidth-message table th,
        .ai-fullwidth-message table td {
          padding: 6px 10px;
          border: 1px solid #E5E7EB;
        }
        .ai-fullwidth-message table tr:nth-child(even) {
          background: #FAFBFC;
        }
        .ai-fullwidth-message img {
          max-width: 280px;
          height: auto;
          border-radius: 6px;
          display: block;
          margin: 8px 0;
        }
        .ai-fullwidth-message p {
          margin: 0 0 8px 0;
        }
        .ai-fullwidth-message p:last-child {
          margin-bottom: 0;
        }
        .ai-fullwidth-message ul,
        .ai-fullwidth-message ol {
          padding-left: 20px;
          margin: 4px 0;
        }
      `}</style>
    </div>
  );
}
