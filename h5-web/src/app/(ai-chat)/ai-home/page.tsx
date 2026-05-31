'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Toast, Swiper, Dialog, ImageViewer } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import { THEME } from '@/lib/theme';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { createChatSession } from '@/lib/chat-session';
import Sidebar from '@/components/ai-chat/Sidebar';
import MoreMenu from '@/components/ai-chat/MoreMenu';
import ConsultTargetPicker, { type FamilyMemberItem } from '@/components/ai-chat/ConsultTargetPicker';
// [PRD-426] 已移除 RecommendCards：原仅服务于"+ 选择咨询人"浮层；首页推荐问改用常驻横向胶囊（见下方 recommended 区块）
import SharePanel from '@/components/ai-chat/SharePanel';
import AiActionBar, { notifyCopied } from '@/components/ai-chat/AiActionBar';
import SectionErrorBoundary from '@/components/SectionErrorBoundary';
import DraggablePunchCard from '@/components/ai-chat/DraggablePunchCard';
import ProfileCard, { clearProfileCardCache } from '@/components/ai-chat/ProfileCard';
import AiAvatar from '@/components/ai-chat/AiAvatar';
import ReminderBellButton from '@/components/ai-chat/ReminderBellButton';
import ReminderDrawer from '@/components/ai-chat/ReminderDrawer';
// [PRD-BELL-UNIFIED-V1 2026-05-19] AI 首页"今日待办"胶囊
import TodayTodoCapsules from '@/components/ai-chat/TodayTodoCapsules';
import { publishBellEvent, subscribeBellEvent } from '@/lib/bell-event-bus';
// [PRD-AIHOME-SKELETON-V1 2026-05-19] 首屏骨架屏：消除刷新跳变
import AiHomeSkeleton from '@/components/ai-chat/AiHomeSkeleton';
import { trackEvent, aiChatTrack, aiHomeFnTrack, type AiChatTargetType } from '@/lib/analytics';
// [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
// 统一按钮意图解析（与后端 button_intent_resolver.py / 小程序 buttonIntent.js 完全一致）
import { resolveButtonIntent } from '@/utils/button-intent';
import { FnCell } from '@/components/design-system';
import { parseServerTime } from '@/lib/datetime';
// [AICHAT-OPTIM-FIX-V1 F-06] ChatCards 调度器
import { resolveCardType, backendButtonToCardButton, ChatCard, type ChatCardType } from '@/components/ai-chat/ChatCards';
// [PRD-AICHAT-CAPSULE-V1 2026-05-15] 输入框上方胶囊条（与菜单模式共用 chat_function_buttons 数据）
import CapsuleBar from '@/components/ai-chat/CapsuleBar';
// [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查抽屉 + 卡片气泡
import HealthSelfCheckDrawer, { type HealthSelfCheckSubmitPayload, type HealthCheckTemplateDetail } from '@/components/ai-chat/HealthSelfCheckDrawer';
import HealthSelfCheckCard from '@/components/ai-chat/HealthSelfCheckCard';
// [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 通用问卷抽屉 + 结果卡片
import QuestionnaireDrawer, {
  type DisplayForm as QnDisplayForm,
  type QnQuestion,
  type QnTemplate,
  type QnSubmitAnswerItem,
} from '@/components/ai-chat/QuestionnaireDrawer';
import QuestionnaireResultCard, { type QnResultCardPayload } from '@/components/ai-chat/QuestionnaireResultCard';
import QuestionnaireRecommendCard, { type RecommendGoodsItem } from '@/components/ai-chat/QuestionnaireRecommendCard';
import UniversalQuestionnaireResultCard from '@/components/ai-chat/UniversalQuestionnaireResultCard';
import FollowupChipsRow from '@/components/ai-chat/FollowupChipsRow';
import WelcomeSection from '@/components/ai-chat/WelcomeSection';
import QuickActionPanel from '@/components/ai-chat/QuickActionPanel';
import HistorySessionBar from '@/components/ai-chat/HistorySessionBar';
import InterruptedBar from '@/components/ai-chat/InterruptedBar';
import RecommendGoodsDrawer from '@/components/ai-chat/RecommendGoodsDrawer';
import QuestionnairePreCard from '@/components/ai-chat/QuestionnairePreCard';
// [BUG_FIX_拍照识药三联_20260516] 聊天内嵌识药引擎：识药结果卡片
import DrugIdentifyCard from './components/DrugIdentifyCard';
// [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 加入 / 查看用药计划抽屉
import AddMedicationDrawer from './components/AddMedicationDrawer';
import ViewMedicationPlansDrawer from './components/ViewMedicationPlansDrawer';
// [PRD-MED-PLAN-INTERACT-OPTIM-V1 2026-05-18] 重新拍照 + 识别失败抽屉
import RetakePhotoDrawer from './components/RetakePhotoDrawer';
import RecognizeFailDrawer from './components/RecognizeFailDrawer';
// [Bug-471 2026-05-15] AI 对话卡片 / 胶囊「相册 / 拍照 / 本机 / 微信」共用的文件选择 + 上传工具
import {
  pickFilesViaHiddenInput,
  uploadImageToServer,
  uploadFileToServer,
} from '@/lib/upload-utils';

// ──────────────────────────────────────────────────────────────────────
// [BUG_FIX_AI_HOME_ACTIONBAR_AND_ATTACHMENT_FILTER_20260517 · Bug-2]
// AI 回复正文清洗 & 图片缩略图抽离工具
//
// Bug 现象（DB 中存在脏数据）：AI 回复正文里偶尔出现两类不应外露的内容
//   1) 图片裸链接 URL（含 markdown 形态 `![](url)`） → 应渲染为可点击放大的小缩略图卡片
//   2) 内部协议提示语 `请参考下面相关附件：\n[附件 xxx 已保存到工作目录:
//      .chat_attachments/xxx]` → 整段过滤掉不显示
//
// 后端入库前已做相同正则清洗（方案②），这里前端兜底是为了应对 DB 历史脏数据
// （DB 不动，靠前端兜底渲染干净）。
// ──────────────────────────────────────────────────────────────────────
const ATTACHMENT_HINT_RE =
  /请参考下面相关附件[:：]\s*\n*\s*\[附件\s+[A-Za-z0-9_\-\.]+\s+已保存到工作目录:\s*\.chat_attachments\/[^\]]+\]/g;

function sanitizeAiContent(raw: string): string {
  if (!raw) return raw;
  return raw.replace(ATTACHMENT_HINT_RE, '').replace(/\n{3,}/g, '\n\n').trim();
}

const IMG_URL_RE = /(https?:\/\/[^\s)\]\"']+?\.(?:png|jpg|jpeg|gif|webp)(?:\?[^\s)\]\"']*)?)/gi;
const MD_IMG_RE = /!\[[^\]]*\]\(([^)]+)\)/g;

/**
 * 从 AI 回复正文里抽离图片 URL（Markdown 形态 + 裸链接），
 * 返回剔除图片占位后的纯文本 + 去重后的图片 URL 数组。
 * 用于在文本下方渲染并排小缩略图（80×80）。
 */
function extractImagesFromContent(raw: string): { text: string; images: string[] } {
  if (!raw) return { text: raw, images: [] };
  const images: string[] = [];
  let text = raw.replace(MD_IMG_RE, (_, url) => {
    if (url) images.push(String(url).trim());
    return '';
  });
  text = text.replace(IMG_URL_RE, (url) => {
    images.push(url);
    return '';
  });
  text = text.replace(/\n{3,}/g, '\n\n').trim();
  const dedup = Array.from(new Set(images.filter(Boolean)));
  return { text, images: dedup };
}

function openAiHomeImageViewer(images: string[], defaultIndex: number) {
  try {
    ImageViewer.Multi.show({
      images,
      defaultIndex: Math.max(0, Math.min(defaultIndex, images.length - 1)),
    });
  } catch {}
}

/**
 * [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F1~F3 2026-05-18]
 * 识药卡片"分阶段渐进淡入"——已升级 messageId 的曾经被渲染过、可立刻全可见，
 * 模块级缓存避免历史会话重进时重复触发渐进。
 */
const _drugCardProgressiveCache = new Set<string>();

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  time: string;
  isStreaming?: boolean;
  /**
   * [BUG_FIX_AI_HOME_ACTIONBAR_AND_ATTACHMENT_FILTER_20260517 · Bug-1]
   * 流式结束 done 事件里 id 会被替换成后端持久化的 message_id；为了让流读完后
   * 的"兜底置回 isStreaming=false"仍能匹配到这条消息，done 时把原乐观 id 记
   * 录在这个字段上，兜底用「原 id 或新 id」双重匹配。
   */
  __origAiMsgId?: string;
  /** [PRD-432] 该消息绑定的咨询对象 family_member_id，AI 回答顶部档案卡片用 */
  consultantTargetId?: number | null;
  /** [PRD-433 F-14] 参考资料：仅当数组非空时渲染，接口未返回则不显示 */
  references?: Array<{ title: string; url?: string }>;
  /**
   * [PRD-AICHAT-CAPSULE-V2 2026-05-15] 消息种类：
   *  - undefined / 'text' : 普通文本
   *  - 'image' : 用户上传的图片消息（content = 图片 URL 或 base64；多图见 images 字段）
   *  - 'file'  : 用户上传的非图片文件消息（content = 文件名占位，files 字段携带文件元数据）
   *  - 'quick_ask_card' : 可编辑的快捷提问卡片消息（quickAskButton 字段携带按钮元数据）
   */
  kind?: 'text' | 'image' | 'file' | 'quick_ask_card' | 'health_self_check_card' | 'questionnaire_result_card' | 'questionnaire_pre_card' | 'questionnaire_recommend_card' | 'followup_chips' | 'system_switch_notice';
  /**
   * [Bug-471 2026-05-15] 用户消息支持 1~5 张图片：图片 URL 数组（服务器返回）。
   * 当 kind === 'image' 且 images 非空时，气泡渲染为「横向缩略图小图墙」。
   * 兼容存量数据：若 images 为空但 content 是 URL/base64，则按单图渲染。
   */
  images?: string[];
  /** [Bug-471 2026-05-15] 用户上传的非图片文件元信息（kind === 'file' 时使用） */
  files?: Array<{ url: string; name: string; size?: number }>;
  /** quick_ask 卡片消息携带的按钮元数据 */
  quickAskButton?: {
    id: number | string;
    name: string;
    icon?: string;
    presetPrompt?: string;
    autoUserMessage?: string;
  };
  /** quick_ask 卡片消息当前状态：pending（可编辑）/ sent（已发送，置灰）/ cancelled（已取消，置灰） */
  quickAskState?: 'pending' | 'sent' | 'cancelled';
  /**
   * [BUG_FIX_拍照识药三联_20260516] 聊天内嵌识药引擎返回的结构化 meta：
   *   - message_type: 'drug_identify_card' → 渲染识药卡（含药品名/成分/适应症等）
   *   - message_type: 'drug_identify_retake' → 渲染「重新拍照」气泡
   *   - 其他 / null → 普通文本气泡
   * 字段来自后端 SSE done 事件的 meta，通过 sendSSE 写入到对应 assistant 消息上。
   */
  drugMeta?: {
    message_type?: 'drug_identify_card' | 'drug_identify_retake' | string;
    medicines?: Array<{
      name?: string;
      brand?: string;
      spec?: string;
      manufacturer?: string;
      category?: string;
      ingredients?: string;
      usage?: string;
      indications?: string;
      precautions?: string;
      contraindications?: string;
    }>;
    family_member_id?: number | null;
    confidence?: number;
    consistency_score?: number;
    reason?: string;
    candidates?: any[];
    // [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517]
    member_name?: string;
    personalized_risk?: {
      level: 'safe' | 'caution' | 'danger';
      label: string;
      conclusion: string;
      reasons?: string[];
    };
    /** [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-3] 已加入用药计划标记 */
    added_to_plan?: boolean;
    [k: string]: any;
  } | null;
  /** [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 自查卡片气泡 payload */
  healthSelfCheck?: {
    archiveId?: number | null;
    archiveName?: string;
    archiveAge?: number | null;
    archiveGender?: string | null;
    bodyPart?: { id: number; name: string; icon: string };
    symptoms?: string[];
    duration?: string;
    templateId?: number;
    buttonId?: number;
    // [PRD-HSC-SSE 2026-05-16] 补充症状描述（选填）
    symptomDescription?: string;
  };
  /** [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 通用问卷结果卡片 payload */
  questionnaireResult?: {
    answerId: number;
    templateId: number;
    buttonId: number;
    card: QnResultCardPayload;
    aiStatusText?: string | null;
    /** [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 后端通用卡片协议 payload */
    universalCard?: any;
  };
  /** [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 追问 chips 行 payload（AI 侧） */
  followupChips?: {
    chips: Array<{ code: string; label: string }>;
    questionnaireResultId?: number;
    templateCode?: string;
    /** 用户点击后置灰收起 */
    disabled?: boolean;
  };
  /** [PRD-TAG-RECOMMEND-V1 2026-05-20] 问卷完成后推荐商品卡片 payload */
  questionnaireRecommend?: {
    goods: Array<{
      id: number;
      name: string;
      sale_price: number;
      original_price?: number | null;
      image?: string | null;
      fulfillment_type?: string | null;
      fulfillment_label?: string | null;
      sales_count?: number;
    }>;
    clickMode: 'drawer' | 'external';
  };
  /** [PRD-TCM-DRAWER-V12 2026-05-20] 通用问卷"对话内说明卡片" payload */
  questionnairePreCard?: {
    buttonId: number;
    templateId?: number | null;
    templateCode?: string | null;
    title: string;
    subtitle?: string | null;
    coverImage?: string | null;
    description?: string | null;
    buttonText?: string;
    icon?: string | null;
    iconType?: string | null;
    // [PRD-AICHAT-FUNCCARD-V2 2026-05-20] 按钮副说明文字
    buttonSubDesc?: string | null;
  };
}

interface Banner {
  id: number;
  image_url: string;
  link_url?: string;
  title?: string;
}

// [AICHAT-OPTIM-FIX-V1 2026-05-14] 扩展 8 个新字段以支持完整卡片调度
interface FunctionButton {
  id: string | number;
  name: string;
  icon?: string;
  icon_url?: string;
  button_type: string;
  params?: Record<string, any>;
  // [AICHAT-OPTIM-FIX-V1 F-07] 8 个新字段（用于卡片调度）
  prompt_template_id?: number | null;
  external_url?: string | null;
  preset_prompt?: string | null;
  auto_user_message?: string | null;
  card_title?: string | null;
  card_subtitle?: string | null;
  card_cover_image?: string | null;
  button_sub_desc?: string | null;
  // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查 4 字段
  health_check_template_id?: number | null;
  archive_missing_strategy?: string | null;
  prompt_override_enabled?: boolean | null;
  prompt_override_text?: string | null;
  sort_weight?: number;
  is_enabled?: boolean;
  // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 两个独立开关：是否推荐 / 是否胶囊
  is_recommended?: boolean;
  is_capsule?: boolean;
  // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 5 个新字段
  grid_sort?: number;
  capsule_sort?: number;
  ai_function_type?: string | null;
  ai_opening?: string | null;
  pre_card_for_navigate?: boolean | null;
  // [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 / PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19]
  questionnaire_template_id?: number | null;
  capture_purpose?: string | null;
  pre_card_enabled?: boolean | null;
  questionnaire_display_form?: string | null;
  // [PRD-QUESTIONNAIRE-DRAWER-V1.2 2026-05-20] 引导卡片三字段
  pre_card_icon?: string | null;
  pre_card_icon_type?: string | null;
  // [PRD-TCM-DRAWER-V12 2026-05-20] 触发开关 + AI 引用开关 + 关键词
  trigger_by_keyword?: boolean | null;
  trigger_by_intent?: boolean | null;
  trigger_keywords?: string[] | null;
  ai_reference_passive?: boolean | null;
  ai_reference_active?: boolean | null;
}

// [PRD-AICHAT-HOME-GRID-V1 2026-05-16] AI 对话首页功能宫格专属 5 色循环配色池（去玫红版方案 A）
// 顺序按 PRD §5.4.1：天蓝青 / 蓝绿青 / 靛蓝 / 紫罗兰 / 青绿
const AI_GRID_COLORS: Array<{ main: string; bg: string }> = [
  { main: '#0EA5E9', bg: '#E0F2FE' },
  { main: '#06B6D4', bg: '#CFFAFE' },
  { main: '#6366F1', bg: '#E0E7FF' },
  { main: '#8B5CF6', bg: '#EDE9FE' },
  { main: '#14B8A6', bg: '#CCFBF1' },
];

const getAiGridColor = (index: number): { main: string; bg: string } =>
  AI_GRID_COLORS[((index % AI_GRID_COLORS.length) + AI_GRID_COLORS.length) % AI_GRID_COLORS.length];

// [PRD-AICHAT-HOME-GRID-V1 2026-05-16] button_type → 内置 emoji 兜底（icon_url / icon 都为空时使用）
const AI_TYPE_ICON_MAP: Record<string, string> = {
  health_self_check: '🩺',
  report_interpret: '📋',
  quick_ask: '💬',
  photo_recognize_drug: '💊',
  drug_identify: '💊',
  photo_upload: '📷',
  file_upload: '📎',
  ai_chat_trigger: '✨',
  ai_dialog_trigger: '✨',
  external_link: '🔗',
  digital_human_call: '👤',
};

// [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 图标三级兜底：icon_url（图片）> icon（emoji）> button_type 自动匹配
function resolveAiGridIcon(btn: FunctionButton): { type: 'image' | 'emoji'; value: string } {
  if (btn.icon_url && typeof btn.icon_url === 'string' && btn.icon_url.trim()) {
    return { type: 'image', value: btn.icon_url };
  }
  if (btn.icon && typeof btn.icon === 'string' && btn.icon.trim()) {
    return { type: 'emoji', value: btn.icon };
  }
  return { type: 'emoji', value: AI_TYPE_ICON_MAP[btn.button_type] || '🔘' };
}

interface FamilyMember {
  id: number;
  nickname: string;
  relationship_type?: string;
  relation_type_name?: string;
  avatar?: string;
  is_self: boolean;
}

// [PRD-467] AI 对话首页字号设置（与「菜单模式·AI 健康咨询页」字号设置打通体验）
// 后端接口 /api/user/font-setting 用 font_size_level：'standard' | 'large' | 'extra_large'
// 实际数值与会话页保持一致：standard=14 / large=18 / extra_large=22
type FontSizeLevel = 'standard' | 'large' | 'extra_large';

const FONT_SIZE_MAP: Record<FontSizeLevel, number> = {
  standard: 14,
  large: 18,
  extra_large: 22,
};

const FONT_LABEL_MAP: Record<FontSizeLevel, string> = {
  standard: '标准',
  large: '大',
  extra_large: '超大',
};

const FONT_TOAST_MAP: Record<FontSizeLevel, string> = {
  standard: '已切换为标准字体',
  large: '已切换为大字体',
  extra_large: '已切换为超大字体',
};

const FUNCTION_ROUTES: Record<string, string> = {
  'view_report': '/checkup',
  'check_drug': '/drug',
  // [PRD-AI-PAGE-OPTIM-V1 2026-05-21 Bug-1/2] 健康档案入口统一指向 /health-profile，旧 /health-archive 已下线
  'view_archive': '/health-profile',
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
      archive_path: '/health-profile',
    },
  },
  session: {
    idle_timeout_minutes: 60,
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
      { id: 'g1', main_text: 'AI诊室', sub_text: '智能问诊', target_path: '/ai-doctor', icon: '🩺', gradient_start: '#0EA5E9', gradient_end: '#8B9AFF', badge: '', enabled: true, sort: 1 },
      { id: 'g2', main_text: '看报告', sub_text: '解读体检报告', target_path: '/checkup', icon: '📋', gradient_start: '#FF7E5F', gradient_end: '#FEB47B', badge: '', enabled: true, sort: 2 },
      { id: 'g3', main_text: '健康档案', sub_text: '查看个人档案', target_path: '/health-profile', icon: '📁', gradient_start: '#43E97B', gradient_end: '#38F9D7', badge: '', enabled: true, sort: 3 },
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
  const d = parseServerTime(iso);
  if (!d) return '';
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  return `${hh}:${mm}`;
}

// [PRD-433 F-09] 微信式时间分隔条文案：今天 HH:mm / 昨天 HH:mm / 周X HH:mm / YYYY/MM/DD HH:mm
function formatWeChatTime(iso: string): string {
  const d = parseServerTime(iso);
  if (!d) return '';
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
  return (parseServerTime(curr)?.getTime() ?? 0) - (parseServerTime(prev)?.getTime() ?? 0) > 5 * 60 * 1000;
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
  const { user, isLoggedIn } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [consultantOpen, setConsultantOpen] = useState(false);
  const [quickActionOpen, setQuickActionOpen] = useState(false);

  // [PRD-MODE-CAPSULE-V1 2026-05-31] AI 首页右上角「模式切换」下拉胶囊：展开/收起状态
  const [modeDropdownOpen, setModeDropdownOpen] = useState(false);
  const [modeSwitching, setModeSwitching] = useState(false);
  const modeDropdownRef = useRef<HTMLDivElement>(null);

  // [PRD-467 FR-02~FR-06] 字号设置：popover 开关 + 当前字号 + 锚点引用 + 300ms debounce 保存
  const [fontPopoverOpen, setFontPopoverOpen] = useState(false);
  const [fontSizeLevel, setFontSizeLevel] = useState<FontSizeLevel>('standard');
  const fontPopoverRef = useRef<HTMLDivElement>(null);
  const fontSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // [PRD-439 F-02/F-04] 提醒抽屉 + 徽标
  const [reminderOpen, setReminderOpen] = useState(false);
  // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F11 2026-05-18]
  // 识药卡底部「用药提醒」按钮触发的抽屉：可指定按某个咨询人 ID 筛选
  const [reminderDrawerConsultantId, setReminderDrawerConsultantId] = useState<number | null>(null);
  // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F10] 各咨询人的"今日是否有未打卡用药提醒"红点缓存
  // key = consultantId (0 表示本人)，value = true 表示有红点
  const [reminderRedDotMap, setReminderRedDotMap] = useState<Record<number, boolean>>({});
  // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F10] 各咨询人是否"无任何用药计划"（按钮置灰）
  const [reminderEmptyMap, setReminderEmptyMap] = useState<Record<number, boolean>>({});
  // [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19] 各咨询人今日用药数据是否仍在加载（首屏防红点闪烁）
  // key=cid; true=loading 中（红点不显示）；false=数据已到位（按 reminderEmptyMap 计算）
  const [reminderLoadingMap, setReminderLoadingMap] = useState<Record<number, boolean>>({});
  // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F6] 识药消息保留的原图（用于整次重试，会话生命周期内有效）
  const [drugRetryImageMap, setDrugRetryImageMap] = useState<Record<string, string[]>>({});

  // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F1~F3] 识药卡片"分阶段渐进淡入"可见性状态
  // 当 drugMeta 第一次进入消息时，由 useEffect 按时间窗依次释放 usage / safety / risk 三卡
  const [drugCardVisibleSectionsMap, setDrugCardVisibleSectionsMap] = useState<
    Record<string, { basic: boolean; usage: boolean; safety: boolean; risk: boolean }>
  >({});
  // [PRD-AIHOME-OPTIM-V1 2026-05-17 R1] 本次优化后铃铛不再显示数字徽标（红点提示移到汉堡图标）。
  // 但 ReminderDrawer 内部仍依赖 refreshReminderBadge 在抽屉打开/关闭时同步徽标状态，故保留 state 与 setter。
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
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

  // [PRD-BELL-UNIFIED-V1 2026-05-19] 订阅全局事件总线：badge:refresh / 切回前台时同步铃铛数字
  useEffect(() => {
    const unsub = subscribeBellEvent('badge:refresh', () => refreshReminderBadge());
    const onVisible = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
        refreshReminderBadge();
      }
    };
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisible);
    }
    // 首次进入时也拉一次
    refreshReminderBadge();
    return () => {
      unsub();
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisible);
      }
    };
  }, [refreshReminderBadge]);

  // 顶部欢迎面板（欢迎区/健康贴士/功能宫格/推荐问）改为常驻瀑布流：
  // 始终位于文档流顶部，与消息列表一起自然向下排布、整体滚动；
  // 不再有折叠态、不再有右上角圆形小康头像悬浮按钮、不再有"收起/展开"切换。
  const messageScrollRef = useRef<HTMLDivElement>(null);

  const [banners, setBanners] = useState<Banner[]>([]);
  const [funcButtons, setFuncButtons] = useState<FunctionButton[]>([]);
  // [PRD-AIHOME-SKELETON-V1 2026-05-19] 首屏加载状态机：
  //   'loading' → 显示骨架屏 + shimmer 动画
  //   'failed'  → 骨架屏内显示「加载失败，点击重试」卡片
  //   'ready'   → 真实内容淡入，骨架屏淡出
  // 关键接口（function-buttons + family/members）齐了即可消失。
  // 5 秒兜底超时；次要接口失败不影响首屏切换。
  type FirstScreenStatus = 'loading' | 'ready' | 'failed';
  const [firstScreenStatus, setFirstScreenStatus] = useState<FirstScreenStatus>('loading');
  // 启动淡出动画的标志（true → 骨架屏 fade-out + 内容 fade-in 同时进行 200ms）
  const [skeletonFading, setSkeletonFading] = useState(false);
  // 关键接口重试触发器：递增即重新执行关键接口 effect
  const [firstScreenRetryNonce, setFirstScreenRetryNonce] = useState(0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  // [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 4.1] 胶囊 upload ActionSheet 开关
  const [capsuleUploadSheetOpen, setCapsuleUploadSheetOpen] = useState(false);
  // [PRD-426] 已移除 inputFocused 状态：原仅用于控制"+ 选择咨询人"浮层显隐，浮层删除后无需此状态
  // [PRD-AICHAT-CAPSULE-V1 2026-05-15] 输入框 focus 时隐藏胶囊条（PRD §3.1 键盘联动）
  const [isInputFocused, setIsInputFocused] = useState(false);
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  // [BUG-466 (2026-05-11)] 用 ref 同步保存"当前最新 sessionId"
  // 切片瞬间 / 异步 await 期间，闭包里读到的 React state 可能仍是旧值，
  // 而 currentSidRef 是同步赋值，所有判断、发送都以它为准，彻底规避
  // "切换瞬间发送被串到旧会话"。任何写入 setSessionId 的位置都必须
  // 先写 currentSidRef.current，再调用 setSessionId（ref 永远领先 state）。
  const currentSidRef = useRef<string | null>(null);
  // [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 跟踪当前会话状态（active / archived）：
  // 当用户点击历史抽屉里某个已归档会话进入时，sidStatusRef = 'archived'；
  // 用户在该会话中按"发送"时，handleSend 必须先调用 /resume 把它变为 active，
  // 同时把任何旧 active 会话归档（后端在 /resume 接口里完成原子事务）。
  const sidStatusRef = useRef<'active' | 'archived' | null>(null);
  const setSidAndRef = useCallback((sid: string | null) => {
    currentSidRef.current = sid;
    setSessionId(sid);
    // 默认设为 active（除非外部显式覆盖）
    sidStatusRef.current = sid ? 'active' : null;
  }, []);
  const [hasHealthTask, setHasHealthTask] = useState(false);
  const [selectedConsultant, setSelectedConsultant] = useState<FamilyMember | null>(null);
  // [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 识药结果加入/查看用药计划抽屉状态
  const [addMedDrawerOpen, setAddMedDrawerOpen] = useState(false);
  const [viewMedDrawerOpen, setViewMedDrawerOpen] = useState(false);
  // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.1] 重新拍照 & 识别失败抽屉控制位
  const [retakeDrawerOpen, setRetakeDrawerOpen] = useState(false);
  const [recogFailDrawerOpen, setRecogFailDrawerOpen] = useState(false);
  const recogTimerRef = useRef<any>(null);
  /** 当前操作的识药卡片来源消息 id（用于乐观更新 added_to_plan 状态） */
  const [activeDrugMsgId, setActiveDrugMsgId] = useState<string | null>(null);
  /** 当前操作的识药卡片数据 */
  const [activeDrugCard, setActiveDrugCard] = useState<any>(null);
  /** [PRD F4] 识药结果"是否已加入"状态：按 `${consultantId}|${drugName}` 缓存 */
  const [drugAddedMap, setDrugAddedMap] = useState<Record<string, boolean>>({});
  // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查抽屉状态
  const [hscDrawerOpen, setHscDrawerOpen] = useState(false);
  const [hscDrawerButton, setHscDrawerButton] = useState<FunctionButton | null>(null);
  const [hscDrawerPrefill, setHscDrawerPrefill] = useState<Partial<HealthSelfCheckSubmitPayload> | null>(null);
  // [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 通用问卷抽屉状态
  const [qnDrawerOpen, setQnDrawerOpen] = useState(false);
  const [qnDrawerLoading, setQnDrawerLoading] = useState(false);
  const [qnDrawerButton, setQnDrawerButton] = useState<FunctionButton | null>(null);
  const [qnDrawerTemplate, setQnDrawerTemplate] = useState<QnTemplate | null>(null);
  const [qnDrawerQuestions, setQnDrawerQuestions] = useState<QnQuestion[]>([]);
  const [qnDrawerDisplayForm, setQnDrawerDisplayForm] = useState<QnDisplayForm>('DRAWER_SCROLL');
  // [PRD-TAG-RECOMMEND-V1 2026-05-20] 推荐商品详情抽屉
  const [recommendDrawerOpen, setRecommendDrawerOpen] = useState(false);
  const [recommendDrawerGoods, setRecommendDrawerGoods] = useState<RecommendGoodsItem | null>(null);
  // [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517] 会话空闲超时由 30 → 60 分钟
  // [PRD-AI-HOME-OPTIM-V4 2026-05-21] 进入页面后会异步从 /api/ai-home/refresh-config 拉取最新阈值
  const [idleTimeout, setIdleTimeout] = useState<number>(60 * 60 * 1000);
  // [PRD-AI-HOME-OPTIM-V4 2026-05-21] 切换咨询人 5 秒撤销期内暂停 60 分钟计时
  const [refreshPaused, setRefreshPaused] = useState<boolean>(false);
  // [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] AI 流式结束的时刻，是 60min 倒计时的起点。
  // 流式输出中不计时（值为 0 时代表当前不应被超时归档）。
  const lastAiDoneAtRef = useRef<number>(0);
  // [Bug-433] lastMsgTime 改为 useRef：避免 React state 异步更新导致 handleSend
  // 在闭包中读到的旧值，从而错误命中"空闲超时清空消息"分支，造成会话首句丢失。
  // 任何写入 setLastMsgTime() 的位置都同步更新此 ref，保证语音/预设按钮等异步入口
  // 在闭包中也能读到最新时间戳。
  const lastMsgTimeRef = useRef<number>(0);
  // [PRD-TCM-DRAWER-V12 2026-05-20] handleSend → insertQuestionnairePreCardMessages 的 ref 桥接
  const insertPreCardRef = useRef<((btn: FunctionButton) => void) | null>(null);
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
  // [PRD-AIHOME-OPTIM-V1 2026-05-17 R3] 汉堡图标右上角红点：未读系统消息数 > 0 OR 待使用订单数 > 0
  // 进入页面时一次性判定，页面停留期间不轮询、不推送；离开页面再回来时重新判定
  const [pendingUseOrderCount, setPendingUseOrderCount] = useState<number>(0);
  // [PRD-AIHOME-OPTIM-V1 2026-05-17 R1] 铃铛初始 top：根据 banner 区域（健康贴士轮播）的位置计算"垂直正中"
  const [bellInitialTop, setBellInitialTop] = useState<number | undefined>(undefined);
  const bannerAnchorRef = useRef<HTMLDivElement>(null);
  // 同一会话期内固定的随机选择
  const [pickedGreeting, setPickedGreeting] = useState<string>('');
  const [pickedSubtitle, setPickedSubtitle] = useState<string>('');

  // [PRD-420] 切换咨询对象 — 蓝色横条撤销功能已移除（M1 需求），保留中央 Toast 和系统消息分割线

  // [PRD-AI-HOME-OPTIM-V4 M2 · F-切人-01] 中央 Toast 浮层（2 秒消失）
  // 文案："已切换为 妈妈 咨询"
  const [centerToastVisible, setCenterToastVisible] = useState(false);
  const [centerToastText, setCenterToastText] = useState('');
  const centerToastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // [PRD-AI-HOME-OPTIM-V4 M3] 右下角小康头像悬浮球状态
  // - floatingPanelOpen：展开面板可见
  // - floatingFirstGuideVisible：首次引导气泡可见（仅展示一次）
  const [floatingPanelOpen, setFloatingPanelOpen] = useState(false);
  const [floatingFirstGuideVisible, setFloatingFirstGuideVisible] = useState(false);

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
    // [PRD-LEGACY-HOME-CLEANUP-V1.1 2026-05-19] 历史 Bug 修复：
    // 原路径 /api/h5/home-banners 404 被 catch 静默吞掉，banner 永远为空数组。
    // 后端正确路径为 /api/home-banners（H5/小程序/Flutter 共用），同时 catch 升级
    // 为 console.warn 兜底，避免下一次再出现"404 被静默吞掉"的隐藏 bug。
    api.get('/api/home-banners').then((res: any) => {
      const data = res.data || res;
      setBanners(Array.isArray(data.items) ? data.items : []);
    }).catch((e) => console.warn('home-banners load failed', e));

    // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 客户端本地缓存 5 分钟
    // - 缓存键：aichat_function_buttons
    // - 命中且未过期：先用缓存数据 setState（秒开），同时后台拉新数据刷新
    // - 未命中 / 过期 / 接口异常：照常拉接口，失败时静默 setFuncButtons([])
    const CACHE_KEY_FB = 'aichat_function_buttons';
    const TTL_FB = 5 * 60 * 1000;
    try {
      const raw = typeof window !== 'undefined' ? window.localStorage.getItem(CACHE_KEY_FB) : null;
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && Array.isArray(parsed.data) && typeof parsed.ts === 'number' && (Date.now() - parsed.ts) < TTL_FB) {
          setFuncButtons(parsed.data as FunctionButton[]);
        }
      }
    } catch {}
    api.get('/api/function-buttons').then((res: any) => {
      const data = res.data || res;
      const arr: FunctionButton[] = Array.isArray(data) ? data
        : Array.isArray(data?.items) ? data.items : [];
      setFuncButtons(arr);
      try {
        if (typeof window !== 'undefined') {
          window.localStorage.setItem(CACHE_KEY_FB, JSON.stringify({ ts: Date.now(), data: arr }));
        }
      } catch {}
    }).catch(() => {
      // 接口异常静默：宫格区会显示内置 3 项兜底（FALLBACK_CONFIG.func_grid.items）
      // 注意：若本地缓存已注入，此处不要 setFuncButtons([]) 覆盖
    });

    // [BUG-FIX 2026-05-16] 接口名拼写错误：today-tasks → today-todos（与后端实际接口、小程序、Flutter 端保持一致）
    api.get('/api/health-plan/today-todos').then((res: any) => {
      const data = res.data || res;
      const totalCount = typeof data.total_count === 'number' ? data.total_count : 0;
      setHasHealthTask(totalCount > 0 || !!data.has_tasks);
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

  // [PRD-AIHOME-SKELETON-V1 2026-05-19] 关键接口并发 effect（功能宫格 + 咨询人）
  //  - 两个接口 Promise.all 完成 → 触发淡出 → 200ms 后切换到真实内容
  //  - 任一关键接口失败 / 5 秒超时 → 显示「加载失败，点击重试」卡片
  //  - 重试时递增 firstScreenRetryNonce 重新执行本 effect
  //  - 次要接口（banner、配置、健康贴士、提醒徽标、未读数等）在各自原有 effect 中
  //    继续以 .catch 静默吞掉异常，不阻塞首屏切换
  useEffect(() => {
    // 重试时把状态重置回 loading
    if (firstScreenRetryNonce > 0) {
      setFirstScreenStatus('loading');
      setSkeletonFading(false);
    }
    let cancelled = false;
    const timeoutId = window.setTimeout(() => {
      if (!cancelled) {
        // 超过 5 秒未返回 → 失败兜底
        setFirstScreenStatus((prev) => (prev === 'loading' ? 'failed' : prev));
      }
    }, 5000);

    Promise.all([
      api.get('/api/function-buttons'),
      api.get('/api/family/members'),
    ])
      .then(() => {
        if (cancelled) return;
        window.clearTimeout(timeoutId);
        // 关键接口已回来——具体写入 state 由原有 effect 完成（避免重复写入）
        // 这里只负责切换骨架屏状态
        setSkeletonFading(true);
        window.setTimeout(() => {
          if (!cancelled) setFirstScreenStatus('ready');
        }, 200);
      })
      .catch(() => {
        if (cancelled) return;
        window.clearTimeout(timeoutId);
        setFirstScreenStatus('failed');
      });

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [firstScreenRetryNonce]);

  // 重试关键接口：递增 nonce → 触发上面 effect 重跑
  const handleRetryFirstScreen = useCallback(() => {
    setFirstScreenRetryNonce((n) => n + 1);
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

  // [PRD-AIHOME-OPTIM-V1 2026-05-17 R3] 进入 /ai-home 时一次性拉取「待使用订单数」
  // 用于与未读系统消息数联合判定汉堡图标右上角红点显示。失败静默（0 → 不影响判定）
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = typeof window !== 'undefined' ? localStorage.getItem('token') : '';
        if (!token) return;
        const res: any = await api.get('/api/orders/unified/counts');
        const data = res?.data ?? res;
        // v2_pending_use 包含 pending_appointment / appointed / pending_use / partial_used
        // 即用户视角"待使用"全部状态；该字段为后端 V2 标准聚合维度
        const cnt = typeof data?.v2_pending_use === 'number'
          ? data.v2_pending_use
          : (typeof data?.pending_use === 'number' ? data.pending_use : 0);
        if (!cancelled && typeof cnt === 'number' && cnt >= 0) {
          setPendingUseOrderCount(cnt);
        }
      } catch {
        // 接口异常静默：待使用订单数视为 0
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

  // [PRD-AI-HOME-OPTIM-V4 2026-05-21] M1 · 60 分钟定时刷新机制
  //
  // F-刷新-01：进入页面时根据 (now - updated_at) 是否 ≥ 阈值决定是否清空旧会话
  // F-刷新-02：加载到旧会话后立即把 lastAiDoneAtRef 初始化为 updated_at（修复 R2，
  //           原本仅在 SSE 完成时赋值，新挂载页面始终为 0 导致后续 idleArchiveCheck 短路）
  // F-刷新-03：阈值统一使用 idleTimeout（来自后端 /api/ai-home/refresh-config，默认 60min）
  const loadLastSession = async () => {
    try {
      const res: any = await api.get('/api/chat/sessions', { params: { limit: 1, sort: '-updated_at' } });
      const data = res.data || res;
      const list = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : []);
      if (list.length === 0) {
        // 用户从未发起会话 → 走默认欢迎页
        return;
      }
      const session = list[0];
      const sid = String(session.id);
      const updatedAtMs = parseServerTime(session.updated_at || session.created_at)?.getTime() ?? 0;

      // [PRD-AI-HOME-OPTIM-V4 F-刷新-01] 关键修复：进入页面时先做时效判断
      // 距上次活跃 ≥ 60min → 不加载旧会话，直接展示空欢迎页
      if (updatedAtMs > 0 && Date.now() - updatedAtMs >= idleTimeout) {
        // 触发埋点：refresh_triggered（mounted 入口）
        try {
          api.post('/api/ai-home/track', {
            event: 'refresh_triggered',
            platform: 'h5',
            payload: {
              trigger_source: 'mounted',
              idle_minutes: Math.round((Date.now() - updatedAtMs) / 60000),
            },
          }).catch(() => {});
        } catch {}
        // 不加载旧会话；保持空 messages + 空 sessionId
        return;
      }

      // 距上次活跃 < 60min → 加载旧会话
      try {
        api.post('/api/ai-home/track', {
          event: 'refresh_skipped',
          platform: 'h5',
          payload: {
            last_active_minutes: updatedAtMs > 0 ? Math.round((Date.now() - updatedAtMs) / 60000) : 0,
          },
        }).catch(() => {});
      } catch {}

      setSidAndRef(sid);
      setLastMsgTime(updatedAtMs);
      await loadSessionMessages(sid);

      // [PRD-AI-HOME-OPTIM-V4 F-刷新-02] 关键修复 R2：用服务端 updated_at 初始化倒计时基准
      // 这样即便用户后续切回页面 / 切回 Tab，idleArchiveCheck 也能正确判断超时
      if (updatedAtMs > 0) {
        lastAiDoneAtRef.current = updatedAtMs;
      }

      // [BUG_FIX_AI_HOME_3BUGS_20260517 · Bug B/C]
      // 自动回到上次会话时也要从权威源回填咨询人（family_member_id）
      try {
        const detailRes: any = await api.get(`/api/chat/sessions/${sid}`);
        const detail = detailRes?.data ?? detailRes;
        const fmBrief = detail?.family_member;
        const fmId: number | null | undefined = detail?.family_member_id;
        if (!fmBrief || !fmId) {
          setSelectedConsultant(null);
        } else {
          const isSelf = !!(fmBrief.is_self || fmBrief.relationship === '本人');
          if (isSelf) {
            setSelectedConsultant(null);
          } else {
            setSelectedConsultant({
              id: fmBrief.id,
              nickname: fmBrief.nickname || '家庭成员',
              relationship_type: fmBrief.relationship,
              relation_type_name: fmBrief.relationship,
              avatar: fmBrief.avatar,
              is_self: false,
            });
          }
        }
      } catch {
        // 详情拉取失败不阻塞
      }
    } catch {}
  };

  const loadSessionMessages = async (sid: string) => {
    try {
      const res: any = await api.get(`/api/chat/sessions/${sid}/messages`);
      const data = res.data || res;
      const list = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : []);
      if (list.length > 0) {
        const mapped: ChatMessage[] = list.map((m: any) => {
          // [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-3]
          // 从 message_metadata 还原 drugMeta，让识药卡片在跨刷新 / 跨设备时完整保留，
          // 并保留 added_to_plan 状态（"已加入用药计划"按钮置灰）
          const meta = m.message_metadata || null;
          const isDrug = meta && (meta.message_type === 'drug_identify_card' || meta.message_type === 'drug_identify_retake');
          return {
            id: String(m.id),
            role: m.role === 'user' ? 'user' as const : 'assistant' as const,
            content: m.content || '',
            time: m.created_at || new Date().toISOString(),
            drugMeta: isDrug ? meta : null,
          };
        });
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
    setSidAndRef(res.sessionId);
    return res.sessionId;
  };

  // [Bug-433 / BUG-466] checkIdleAndMaybeNewSession 接受可选的 preserveOnClear 回调：
  // 当命中"空闲超时清空消息"分支时，外部（handleSend）可以通过该参数把
  // 即将插入的乐观渲染 userMsg 回填到清空后的列表中，避免会话首句被一并清掉。
  // 同时 lastMsgTime 与 sessionId 均改为从 ref 读取，避免闭包过期导致：
  //   1. "语音/预设按钮首句"误清空（Bug-433）
  //   2. 切换咨询对象的同一帧内按下发送时，sid 闭包还是旧值（BUG-466 根因 C）
  const checkIdleAndMaybeNewSession = async (
    preserveOnClear?: () => ChatMessage[],
  ): Promise<string> => {
    const now = Date.now();
    const lmt = lastMsgTimeRef.current;
    const sid = currentSidRef.current;
    if (sid && lmt && (now - lmt) > idleTimeout) {
      // [BUG-466 发送前最后一道兜底] 距上次活动超阈值 → 强制开新会话
      const preserve = preserveOnClear ? preserveOnClear() : [];
      setMessages(preserve);
      currentSidRef.current = null;
      setSessionId(null);
      try {
        window.dispatchEvent(new Event('bh-history-refresh'));
      } catch {
        /* ignore */
      }
      const newSid = await createNewSession();
      return newSid || sid;
    }
    if (!sid) {
      const newSid = await createNewSession();
      return newSid || '';
    }
    return sid;
  };

  // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
  // 报告解读 / 识药等场景需要把按钮意图与图片 URL 列表显式透传给后端，
  // 避免后端只能从 content 文本里抽 URL、且无法区分"普通图片消息"与"报告解读"。
  type SsePayloadExtras = {
    intent?: string | null;
    imageUrls?: string[] | null;
    buttonType?: string | null;
    buttonId?: number | null;
    reportMeta?: { report_title?: string | null; report_date?: string | null } | null;
    // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
    // 后台 3 层按钮配置透传：ai_function_type / capture_purpose
    aiFunctionType?: string | null;
    capturePurpose?: string | null;
  };

  const sendSSE = async (
    sid: string,
    message: string,
    retries = 3,
    source: 'text' | 'voice' | 'preset' = 'text',
    extras?: SsePayloadExtras,
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

        // [BUG_FIX_拍照识药三联_20260516] 透传 family_member_id（咨询人 ID）：
        // 妈妈给孩子拍药时，剂量/禁忌/相互作用必须基于「咨询人」档案而非登录用户档案，
        // 否则可能给儿童按成人剂量。未选咨询人时该字段为 null，后端会兜底为登录用户档案。
        const fmId = selectedConsultant ? selectedConsultant.id : null;
        const response = await fetch(`${basePath}/api/chat/sessions/${sid}/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            content: message,
            message_type: 'text',
            source,
            family_member_id: fmId,
            // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
            // 透传通用 intent 协议字段，后端按显式优先级分发到对应引擎：
            // - intent='report_interpret' + image_urls → ReportInterpretEngine
            // - intent='drug_identify'    + image_urls → DrugIdentifyEngine
            // 未指定时后端行为完全不变（向后兼容）。
            intent: extras?.intent || undefined,
            image_urls: extras?.imageUrls && extras.imageUrls.length > 0
              ? extras.imageUrls
              : undefined,
            button_type: extras?.buttonType || undefined,
            button_id: extras?.buttonId || undefined,
            report_meta: extras?.reportMeta || undefined,
            // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
            // 新体系按钮 3 层配置透传给后端，前后端双保险兜底解析。
            ai_function_type: extras?.aiFunctionType || undefined,
            capture_purpose: extras?.capturePurpose || undefined,
          }),
          signal: controller.signal,
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No reader');

        const decoder = new TextDecoder();
        let accumulated = '';
        let buffer = '';
        // [BUG_FIX_拍照识药三联_20260516] 跟踪 SSE 事件类型：
        //   - event: progress 仅作为占位提示（用 isStreaming 状态展示）
        //   - event: delta   累积内容
        //   - event: done    解析 meta，识别为 drug_identify_card/retake 时附加到消息
        let currentEvent: 'delta' | 'progress' | 'done' = 'delta';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              const ev = line.substring(7).trim();
              if (ev === 'delta' || ev === 'progress' || ev === 'done') {
                currentEvent = ev as any;
              }
              continue;
            }
            if (line.startsWith('data: ')) {
              const payload = line.substring(6);
              if (payload === '[DONE]') break;
              try {
                const parsed = JSON.parse(payload);
                if (currentEvent === 'progress') {
                  // progress 阶段不污染正文，仅在尚未有 delta 时给一行占位
                  if (!accumulated && parsed.text) {
                    setMessages(prev => prev.map(m =>
                      m.id === aiMsgId ? { ...m, content: parsed.text + '…' } : m
                    ));
                  }
                  continue;
                }
                if (currentEvent === 'done') {
                  const meta = parsed?.meta || null;
                  const fullText = parsed?.full_content || accumulated;
                  // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.1.3] 识药结果到达 → 关闭兜底定时器；
                  //   若是 drug_identify_retake 类型 → 自动弹失败抽屉
                  if (recogTimerRef.current) {
                    clearTimeout(recogTimerRef.current);
                    recogTimerRef.current = null;
                  }
                  if (meta && meta.message_type === 'drug_identify_retake') {
                    setRecogFailDrawerOpen(true);
                  }
                  // [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-3]
                  // 用后端持久化的真实 message_id 替换乐观 id，
                  // 这样后续点击"加入用药计划"才能调 /api/chat/messages/{id}/mark-added-to-plan
                  const persistedId = parsed?.message_id;
                  // [BUG_FIX_AI_HOME_ACTIONBAR_AND_ATTACHMENT_FILTER_20260517 · Bug-1]
                  // 致命根因修复：必须在 done 事件这一次 setMessages 里"原子写入"
                  // isStreaming: false。原代码先把 m.id 从 aiMsgId 替换成了 persistedId，
                  // 然后下面流读完后的兜底 `m.id === aiMsgId` 永远匹配不上，
                  // 导致 isStreaming 永远停留在 true、ActionBar 不显示。
                  // 同时记录 __origAiMsgId 供下方双 id 防御性兜底匹配。
                  setMessages(prev => prev.map(m => (
                    m.id === aiMsgId
                      ? {
                          ...m,
                          id: persistedId ? String(persistedId) : m.id,
                          content: fullText,
                          drugMeta: meta,
                          isStreaming: false,
                          __origAiMsgId: aiMsgId,
                        } as any
                      : m
                  )));
                  // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F6] 保留原图，供"整次识药重试"复用
                  try {
                    const imgUrls: string[] = (meta && Array.isArray(meta.image_urls)) ? meta.image_urls : [];
                    if (imgUrls.length > 0) {
                      const targetId = persistedId ? String(persistedId) : aiMsgId;
                      setDrugRetryImageMap((prev) => ({ ...prev, [targetId]: imgUrls }));
                    }
                  } catch {}
                  continue;
                }
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

        // [BUG_FIX_AI_HOME_ACTIONBAR_AND_ATTACHMENT_FILTER_20260517 · Bug-1]
        // 防御性兜底：done 事件已把 m.id 从 aiMsgId 改成了 persistedId，
        // 这里用「原 id 或新 id（通过 __origAiMsgId 标记）」双重匹配，
        // 确保任何分支下流式结束后 isStreaming 都能被置回 false。
        setMessages(prev => prev.map(m =>
          (m.id === aiMsgId || (m as any).__origAiMsgId === aiMsgId)
            ? { ...m, isStreaming: false }
            : m
        ));
        // [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] AI 流式完成 → 启动 60 分钟倒计时
        lastAiDoneAtRef.current = Date.now();
        abortRef.current = null;
        return true;
      } catch (err: any) {
        if (err.name === 'AbortError') {
          setMessages(prev => prev.map(m =>
            (m.id === aiMsgId || (m as any).__origAiMsgId === aiMsgId)
              ? { ...m, isStreaming: false }
              : m
          ));
          // 流式被打断也视为已结束，启动倒计时
          lastAiDoneAtRef.current = Date.now();
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
  // [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 识药结果"是否已加入"批量刷新
  // 入参 drug_names 来自当前消息列表中所有识药卡片的药品名
  const refreshDrugAddedStatus = useCallback(async (drugNames: string[]) => {
    const consultantId = selectedConsultant?.id ?? 0;
    const unique = Array.from(new Set(drugNames.filter((n) => n && n.trim())));
    if (unique.length === 0) return;
    try {
      const qs = `drug_names=${encodeURIComponent(unique.join(','))}&consultant_id=${consultantId}`;
      const res: any = await api.get(`/api/health-plan/medications/check-batch?${qs}`);
      const data = (res?.data?.data ?? res?.data ?? {}) as Record<string, boolean>;
      setDrugAddedMap((prev) => {
        const next = { ...prev };
        for (const name of unique) {
          next[`${consultantId}|${name}`] = !!data[name];
        }
        return next;
      });
    } catch {
      // 静默
    }
  }, [selectedConsultant]);

  const handleSend = useCallback(async (
    text?: string,
    source: 'text' | 'voice' | 'preset' = 'text',
    opts?: {
      suppressUserBubble?: boolean;
      backendText?: string;
      // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
      // 透传通用 SSE intent 协议字段：报告解读 / 显式识药等
      sseExtras?: SsePayloadExtras;
    },
  ) => {
    const msg = text || inputValue.trim();
    if (!msg || sending) return;

    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = '24px';
    }

    // [PRD-TCM-DRAWER-V12 2026-05-20] 用户文本意图识别（仅 source=text/voice 时拦截）：
    //   命中 questionnaire 类按钮 → 插入用户气泡 + AI 说明卡片，不再走 LLM 流式回复
    if (source !== 'preset') {
      try {
        const detect = await api.post<any>('/api/chat/intent-detect', {
          text: msg,
          consultant_id: selectedConsultant?.id ?? null,
        });
        if (detect && detect.intent && String(detect.intent).startsWith('questionnaire_') && detect.button_id) {
          const btn = funcButtons.find((b) => Number(b.id) === Number(detect.button_id));
          const insertFn = insertPreCardRef.current;
          if (btn && typeof insertFn === 'function') {
            // 先插入用户气泡
            setMessages((prev) => [...prev, {
              id: `u-intent-${Date.now()}`,
              role: 'user',
              content: msg,
              time: new Date().toISOString(),
              kind: 'text',
            }]);
            insertFn(btn);
            setSending(false);
            return;
          }
        }
      } catch (e) {
        // 意图识别失败不影响主流程，继续走 AI 回复
        if (typeof console !== 'undefined') console.warn('[ai-home] intent-detect failed', e);
      }
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

    // [BUG_FIX_拍照识药_v3 2026-05-16] suppressUserBubble=true 时不在对话流追加用户文本气泡
    // （由调用方负责图片气泡的展示），仅把消息体 msg 发给后端用于 AI 上下文。
    const suppressBubble = !!opts?.suppressUserBubble;
    // backendText 优先于 msg 作为发给后端的内容；UI 仍展示 msg（如未抑制气泡）
    const backendPayload = (opts?.backendText && opts.backendText.trim()) || msg;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: msg,
      time: new Date().toISOString(),
    };

    try {
      // [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 已归档会话追问：
      // 用户点击历史会话后 sidStatusRef.current === 'archived'，
      // 此时按下发送 → 先调用 /resume 把该会话激活（同事务把旧 active 归档），
      // 拿到响应后再走原本的 idle 检查/发送流程。
      if (sidStatusRef.current === 'archived' && currentSidRef.current) {
        try {
          await api.post(`/api/chat-sessions/${currentSidRef.current}/resume`);
          sidStatusRef.current = 'active';
          // 重置 idle 倒计时（resume 后新一轮活动开始）
          lastAiDoneAtRef.current = 0;
          // 通知抽屉刷新（被恢复的会话从历史列表消失；被顶替的旧 active 进入今天分组）
          try {
            window.dispatchEvent(new Event('bh-history-refresh'));
          } catch {
            /* ignore */
          }
        } catch {
          // resume 失败，仍尝试继续发送（容错）
        }
      }
      // [Bug-433] 先决定 sid（idle 命中时清空消息），命中时通过 preserveOnClear
      // 把 userMsg 回填到清空后的列表，避免首句被一并抹掉。
      const sid = await checkIdleAndMaybeNewSession(() => (suppressBubble ? [] : [userMsg]));
      if (!sid) {
        if (!suppressBubble) {
          setMessages(prev => (prev.some(m => m.id === userMsg.id) ? prev : [...prev, userMsg]));
        }
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
      // [BUG_FIX_拍照识药_v3 2026-05-16] suppressUserBubble=true 时跳过用户文本气泡渲染
      if (!suppressBubble) {
        setMessages(prev => (prev.some(m => m.id === userMsg.id) ? prev : [...prev, userMsg]));
      }

      const sseOk = await sendSSE(sid, backendPayload, 3, source, opts?.sseExtras);
      if (!sseOk) {
        await sendFallback(sid, backendPayload, source);
      }
    } catch {
      if (!suppressBubble) {
        setMessages(prev => (prev.some(m => m.id === userMsg.id) ? prev : [...prev, userMsg]));
      }
      setMessages(prev => [...prev, {
        id: `e-${Date.now()}`,
        role: 'assistant',
        content: '网络异常，请稍后重试',
        time: new Date().toISOString(),
      }]);
    }
    setSending(false);
    // [BUG-466] 依赖数组移除 sessionId：handleSend 内已统一从 currentSidRef.current
    // 读取最新 sid，闭包不再需要绑定 state；保留 selectedConsultant 是因为
    // createChatSession 内部需要使用最新选定的咨询对象。
  }, [inputValue, sending, selectedConsultant, idleTimeout]);

  /**
   * [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 4.1] 胶囊点击 = 按 button_type 直接触发对应功能
   * - upload类（含 file_upload / photo_upload / photo_recognize_drug / report_interpret）
   *   → 弹「相册 / 拍照」ActionSheet，选完图后对话区出现图片消息 + 触发 AI 回复
   * - ai_chat_trigger / external_link / navigate 类 → 直接执行页面跳转，不在对话区留痕
   * - quick_ask → 在对话区渲染可编辑的 QuickAskCard 消息（用户编辑后点发送）
   * - digital_human_call / sdk_call → 直接调用 SDK 能力（视频通话），不在对话区留痕
   */
  const handleCapsuleByType = useCallback((btn: FunctionButton) => {
    const type = btn.button_type;
    // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 新两大类与宫格保持完全一致行为
    //   - page_navigate：按 pre_card_for_navigate 决定直接跳还是先弹卡片
    //   - ai_function ：先 ai_opening（如有）→ 弹卡片
    if (type === 'page_navigate' || type === 'ai_function') {
      handleFunctionButtonClick(btn);
      return;
    }
    // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查类型：唤起抽屉
    if (type === 'health_self_check') {
      const strategy = btn.archive_missing_strategy || 'use_default';
      if (!selectedConsultant && strategy === 'force_toast') {
        showToast('请先在顶部选择咨询档案', 'warning');
        return;
      }
      setHscDrawerButton(btn);
      setHscDrawerPrefill(null);
      setHscDrawerOpen(true);
      return;
    }
    // upload 类：统一弹 ActionSheet（H5 实现复用现有 file input 选择）
    if (
      type === 'photo_upload' ||
      type === 'file_upload' ||
      type === 'photo_recognize_drug' ||
      type === 'drug_identify' ||
      type === 'medication_recognize' ||
      type === 'report_interpret'
    ) {
      try {
        triggerCapsuleUpload(btn);
      } catch (e) {
        // 兜底：上传链路异常时退化为预设话术发送（旧行为）
        const fb = (btn.preset_prompt || btn.auto_user_message || btn.name || '').trim();
        if (fb) handleSend(fb, 'preset');
      }
      return;
    }

    // navigate / external_link / ai_chat_trigger：直接跳转，不在对话区留痕
    if (type === 'external_link' || type === 'ai_chat_trigger' || type === 'ai_dialog_trigger') {
      const url =
        btn.external_url ||
        (typeof btn.params === 'object' && btn.params ? (btn.params as any).url : null) ||
        '';
      if (url) {
        try {
          if (/^https?:\/\//.test(url)) {
            window.location.href = url;
          } else if (url.startsWith('/')) {
            router.push(url);
          } else {
            router.push(`/${url}`);
          }
        } catch {}
      } else if (FUNCTION_ROUTES[type]) {
        router.push(FUNCTION_ROUTES[type]);
      }
      return;
    }

    // sdk_call（digital_human_call / video_consult 等）：直接调用 SDK，不在对话区留痕
    if (type === 'digital_human_call' || type === 'video_consult' || type === 'live_chat') {
      try {
        if (FUNCTION_ROUTES[type]) {
          router.push(FUNCTION_ROUTES[type]);
        } else {
          router.push('/voice-call');
        }
      } catch {}
      return;
    }

    // quick_ask：插入一条「可编辑快捷提问卡片」消息（用户编辑后点击发送才真正发出）
    if (type === 'quick_ask' || type === 'prompt_template') {
      const preset = (
        btn.preset_prompt ||
        btn.auto_user_message ||
        btn.name ||
        ''
      ).trim();
      const cardMsg: ChatMessage = {
        id: `qa-${Date.now()}`,
        role: 'user',
        content: preset,
        time: new Date().toISOString(),
        kind: 'quick_ask_card',
        quickAskState: 'pending',
        quickAskButton: {
          id: btn.id,
          name: btn.name,
          icon: btn.icon || '⚡',
          presetPrompt: btn.preset_prompt || undefined,
          autoUserMessage: btn.auto_user_message || undefined,
        },
      };
      // 将之前的同类卡片标记为 cancelled（PRD §4.2：未操作发起其他消息时变灰、不可再交互）
      setMessages((prev) =>
        prev
          .map((m) =>
            m.kind === 'quick_ask_card' && m.quickAskState === 'pending'
              ? { ...m, quickAskState: 'cancelled' as const }
              : m,
          )
          .concat(cardMsg),
      );
      return;
    }

    // 默认兜底：以"用户身份"发送预设话术
    const fb = (btn.preset_prompt || btn.auto_user_message || btn.name || '').trim();
    if (fb) {
      lastMsgTimeRef.current = Date.now();
      handleSend(fb, 'preset');
    }
  }, [handleSend, router]);

  /**
   * [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 4.1] upload 类胶囊点击触发的 ActionSheet
   * H5 端通过一个隐藏 <input type=file> 实现「相册」「拍照」二选一（capture 属性区分），
   * 用户选完图后：先在对话区显示「用户：[图片缩略图]」消息，再触发 AI 回复（preset_prompt 兜底）。
   */
  const capsuleUploadBtnRef = useRef<FunctionButton | null>(null);

  const triggerCapsuleUpload = (btn: FunctionButton) => {
    capsuleUploadBtnRef.current = btn;
    setCapsuleUploadSheetOpen(true);
  };

  /**
   * [Bug-471 2026-05-15] AI 对话卡片 / 胶囊「相册 / 拍照 / 本机 / 微信」共用的核心处理函数。
   *
   * 修复点（与 Bug-471 修复方案 §3.2 对齐）：
   *  - 用 pickFilesViaHiddenInput（input 挂到 DOM，避免 iOS Safari / 微信 GC）
   *  - 支持多选；超过 maxCount 时截取并 Toast 提示
   *  - 逐张上传到服务器拿 URL（与 /drug 完全复用）
   *  - 对话区先插入「用户消息（含 1~5 张缩略图）」气泡，再触发 AI 回复
   *  - AI 触发文本取值顺序：preset_prompt → auto_user_message → 按钮 name → 按类型兜底文案
   *
   * 参数：
   *  - source：'album' / 'camera'（'wechat' 由调用方做友好提示后退化到 album）
   *  - kind  ：'image' = 仅图片（拍照识药/普通照片/报告解读）/ 'file' = 含 PDF 等文件
   *  - prompt 取值参数三选一：preset_prompt / auto_user_message / button_name
   *  - fallbackPrompt：按 button_type 推导出的兜底文案（药品类 / 报告类 / 普通图片类 / 文件类）
   */
  const MAX_UPLOAD_IMAGES = 5;

  const pickAndUploadThenSend = useCallback((opts: {
    source: 'album' | 'camera';
    kind: 'image' | 'file';
    presetPrompt?: string | null;
    autoUserMessage?: string | null;
    buttonName?: string | null;
    fallbackPrompt: string;
    // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
    // 按钮类型透传：用于 SSE intent 协议
    //   - 'report_interpret' → intent='report_interpret'，后端走 ReportInterpretEngine
    //   - 'photo_recognize_drug' / 'drug_identify' / 'medication_recognize' → intent='drug_identify'
    buttonType?: string | null;
    buttonId?: number | null;
    // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
    // 后台新体系按钮 3 层配置透传，用于 resolveButtonIntent 统一翻译为 SSE intent
    aiFunctionType?: string | null;
    capturePurpose?: string | null;
  }) => {
    const accept = opts.kind === 'image' ? 'image/*' : 'image/*,application/pdf';
    let loadingToastVisible = false;
    pickFilesViaHiddenInput({
      accept,
      source: opts.source,
      multiple: opts.kind === 'image',
      onPicked: async (files) => {
        if (!files || files.length === 0) return;
        // 截取前 N 张并 Toast 提示
        let picked = files;
        if (opts.kind === 'image' && files.length > MAX_UPLOAD_IMAGES) {
          picked = files.slice(0, MAX_UPLOAD_IMAGES);
          try {
            showToast(`最多 ${MAX_UPLOAD_IMAGES} 张`, 'warning');
          } catch {}
        }
        // 上传 Loading
        try {
          Toast.show({ icon: 'loading', content: '正在上传…', duration: 0 });
          loadingToastVisible = true;
        } catch {}

        const uploadedImages: string[] = [];
        const uploadedFiles: Array<{ url: string; name: string; size?: number }> = [];
        let failedCount = 0;

        for (const f of picked) {
          try {
            const isImage =
              (f.type && f.type.startsWith('image/')) ||
              /\.(png|jpe?g|gif|webp|bmp|heic|heif)$/i.test(f.name || '');
            if (isImage) {
              const url = await uploadImageToServer(f);
              uploadedImages.push(url);
            } else {
              const url = await uploadFileToServer(f);
              uploadedFiles.push({ url, name: f.name || '文件', size: f.size });
            }
          } catch {
            failedCount += 1;
          }
        }

        try {
          if (loadingToastVisible) Toast.clear();
        } catch {}

        const totalOk = uploadedImages.length + uploadedFiles.length;
        if (totalOk === 0) {
          try {
            showToast('图片上传失败，请重试', 'fail');
          } catch {}
          return;
        }
        if (failedCount > 0) {
          try {
            showToast(`${failedCount} 张上传失败，已自动跳过`, 'warning');
          } catch {}
        }

        // 插入用户消息气泡
        const now = new Date().toISOString();
        if (uploadedImages.length > 0) {
          const imgMsg: ChatMessage = {
            id: `img-${Date.now()}`,
            role: 'user',
            content: uploadedImages[0],
            time: now,
            kind: 'image',
            images: uploadedImages,
          };
          setMessages((prev) => prev.concat(imgMsg));
        }
        if (uploadedFiles.length > 0) {
          const fileMsg: ChatMessage = {
            id: `file-${Date.now()}`,
            role: 'user',
            content: uploadedFiles.map((f) => f.name).join('、'),
            time: now,
            kind: 'file',
            files: uploadedFiles,
          };
          setMessages((prev) => prev.concat(fileMsg));
        }

        // 触发 AI 回复
        const prompt = (
          (opts.presetPrompt || '').trim() ||
          (opts.autoUserMessage || '').trim() ||
          (opts.buttonName || '').trim() ||
          (opts.fallbackPrompt || '').trim()
        );
        if (prompt) {
          // [BUG_FIX_拍照识药_v3 2026-05-16] 重写图片/文件 URL 注入策略：
          // 1) UI 上不再多渲染一条「[用户上传的图片N张]+ URL 列表」的冗余文本气泡（Bug #1）。
          // 2) 仍把 URL 信息注入给后端 AI 上下文（backendText），让 AI 能"知道"图片地址。
          // 3) 通过 handleSend 的 suppressUserBubble=true 关闭对话流中文本气泡渲染，
          //    用户视觉只看到「图片小图墙气泡 + AI 回复」两条，符合 PRD 5.1 验收。
          const urlLines: string[] = [];
          if (uploadedImages.length > 0) {
            urlLines.push(
              `[用户上传的图片 ${uploadedImages.length} 张]\n` +
                uploadedImages.map((u, i) => `${i + 1}. ${u}`).join('\n'),
            );
          }
          if (uploadedFiles.length > 0) {
            urlLines.push(
              `[用户上传的文件 ${uploadedFiles.length} 个]\n` +
                uploadedFiles
                  .map((f, i) => `${i + 1}. ${f.name} ${f.url}`)
                  .join('\n'),
            );
          }
          const backendComposed = urlLines.length > 0
            ? `${urlLines.join('\n\n')}\n\n${prompt}`
            : prompt;
          const hasUploaded = uploadedImages.length > 0 || uploadedFiles.length > 0;
          lastMsgTimeRef.current = Date.now();
          // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
          // 使用统一映射器把后台 3 层按钮配置翻译为 SSE intent，
          // 与后端 button_intent_resolver.py 逻辑保持完全一致。
          const sseIntent = resolveButtonIntent({
            button_type: opts.buttonType,
            ai_function_type: opts.aiFunctionType,
            capture_purpose: opts.capturePurpose,
          });
          const sseExtras = sseIntent || uploadedImages.length > 0
            ? {
                intent: sseIntent,
                imageUrls: uploadedImages.length > 0 ? uploadedImages : null,
                buttonType: opts.buttonType || null,
                buttonId: opts.buttonId || null,
                // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
                // 同时透传 ai_function_type / capture_purpose，
                // 后端可做双保险兜底解析。
                aiFunctionType: opts.aiFunctionType || null,
                capturePurpose: opts.capturePurpose || null,
              }
            : undefined;
          setTimeout(() => {
            if (hasUploaded) {
              handleSend(prompt, 'preset', {
                suppressUserBubble: true,
                backendText: backendComposed,
                sseExtras,
              });
            } else {
              handleSend(prompt, 'preset');
            }
          }, 50);
        }
      },
    });
  }, [handleSend]);

  /**
   * 根据 button_type 推导上传后的兜底问题文案。
   *   药品类  → "我上传了一张药品图片，请帮我识别"
   *   报告类  → "我上传了一份体检报告，请帮我解读"
   *   普通图片→ "我上传了一张图片，请你帮我看看"
   *   文件类  → "我上传了一份文件，请你帮我看看"
   */
  const resolveUploadFallbackPrompt = (buttonType: string | undefined, kind: 'image' | 'file'): string => {
    if (kind === 'file') return '我上传了一份文件，请你帮我看看';
    const t = (buttonType || '').toLowerCase();
    if (t === 'photo_recognize_drug' || t === 'drug_identify' || t === 'medication_recognize') {
      return '我上传了一张药品图片，请帮我识别';
    }
    if (t === 'report_interpret') {
      return '我上传了一份体检报告，请帮我解读';
    }
    return '我上传了一张图片，请你帮我看看';
  };

  const handleCapsuleUploadPick = (source: 'album' | 'camera') => {
    setCapsuleUploadSheetOpen(false);
    const btn = capsuleUploadBtnRef.current;
    if (!btn) return;
    const isFileType = btn.button_type === 'file_upload';
    pickAndUploadThenSend({
      source,
      kind: isFileType ? 'file' : 'image',
      presetPrompt: btn.preset_prompt,
      autoUserMessage: btn.auto_user_message,
      buttonName: btn.name,
      fallbackPrompt: resolveUploadFallbackPrompt(btn.button_type, isFileType ? 'file' : 'image'),
      // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517] 透传按钮类型 → SSE intent
      buttonType: btn.button_type,
      buttonId: btn.id as any,
      // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
      // 后台新体系按钮 3 层配置透传，让 resolveButtonIntent 命中 P3/P4 规则
      aiFunctionType: (btn as any).ai_function_type ?? null,
      capturePurpose: (btn as any).capture_purpose ?? null,
    });
  };

  /**
   * [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 4.2] QuickAskCard「发送」按钮回调：
   * - 把用户编辑后的文本以「用户身份」发出，触发 AI 回复
   * - 当前卡片消息置为 sent（变灰、不可再交互）
   */
  const handleQuickAskCardSend = useCallback((cardMsgId: string, text: string) => {
    const trimmed = (text || '').trim();
    if (!trimmed) return;
    setMessages((prev) =>
      prev.map((m) => (m.id === cardMsgId ? { ...m, quickAskState: 'sent' as const, content: trimmed } : m)),
    );
    lastMsgTimeRef.current = Date.now();
    handleSend(trimmed, 'preset');
  }, [handleSend]);

  const handleQuickAskCardCancel = useCallback((cardMsgId: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === cardMsgId ? { ...m, quickAskState: 'cancelled' as const } : m)),
    );
  }, []);

  // [PRD-TCM-DRAWER-V12 2026-05-20] 在对话流插入「用户气泡 + AI 说明卡片气泡」
  // 通过 ref 桥接，让 handleSend（定义更早）能调用本函数（定义更晚）
  const insertQuestionnairePreCardMessages = useCallback(
    (btn: FunctionButton) => {
      const userText = (btn.auto_user_message && btn.auto_user_message.trim()) || `我想做${btn.name || '健康测评'}`;
      const titleText = (btn.card_title && btn.card_title.trim()) || btn.name || '健康测评';
      const subtitleText = (btn.card_subtitle && btn.card_subtitle.trim()) || null;
      // [PRD-AICHAT-FUNCCARD-V2 2026-05-20] description / buttonSubDesc 分离：
      //   - description: 兼容旧字段（继续作为副标题兜底，FunctionCardV2 内部已 fallback）
      //   - buttonSubDesc: 新版样式中"按钮上方的灰色小字"，单独取 button_sub_desc 字段
      const descText = btn.button_sub_desc || null;
      const btnSubDescText = btn.button_sub_desc || null;
      const cover = (btn.card_cover_image && btn.card_cover_image.trim()) || null;
      // 1) 用户气泡：模拟用户主动发起测评
      const userMsg: ChatMessage = {
        id: `qn-pre-user-${Date.now()}`,
        role: 'user',
        content: userText,
        time: new Date().toISOString(),
        kind: 'text',
      };
      // 2) AI 气泡：说明卡片
      const cardMsg: ChatMessage = {
        id: `qn-pre-card-${Date.now() + 1}`,
        role: 'assistant',
        content: titleText,
        time: new Date().toISOString(),
        kind: 'questionnaire_pre_card',
        questionnairePreCard: {
          buttonId: Number(btn.id),
          templateId: btn.questionnaire_template_id || null,
          templateCode: null,
          title: titleText,
          subtitle: subtitleText,
          coverImage: cover,
          description: descText,
          // [PRD-AICHAT-FUNCCARD-V2-DESIGN-D 2026-05-20 v1.2] 决策 12：按钮固定「开始」
          buttonText: '开始',
          icon: btn.pre_card_icon || null,
          iconType: btn.pre_card_icon_type || 'default',
          // [PRD-AICHAT-FUNCCARD-V2 2026-05-20] 按钮副说明文字（v2 卡片"按钮上方灰小字"展示位）
          buttonSubDesc: btnSubDescText,
        },
      };
      setMessages((prev) => [...prev, userMsg, cardMsg]);
      try { aiHomeFnTrack.cardExposure(Number(btn.id), 'questionnaire_pre_card' as any); } catch {}
    },
    [],
  );
  // ref 桥接：handleSend 通过 ref 调用本函数
  useEffect(() => {
    insertPreCardRef.current = insertQuestionnairePreCardMessages;
  }, [insertQuestionnairePreCardMessages]);

  // [PRD-TCM-DRAWER-V12 2026-05-20] 点击说明卡片「开始测评」→ 打开对应问卷抽屉
  const handlePreCardStart = useCallback(
    (data: NonNullable<ChatMessage['questionnairePreCard']>) => {
      const btn = funcButtons.find((b) => Number(b.id) === data.buttonId);
      if (!btn) {
        showToast('按钮已不存在，请刷新页面', 'warning');
        return;
      }
      const displayForm = (btn.questionnaire_display_form || 'DRAWER_SCROLL') as QnDisplayForm;
      // INLINE_CHAT 形态时也用 DRAWER_STEPPED（题量大、一题一屏更友好）
      const effForm: QnDisplayForm =
        displayForm === 'INLINE_CHAT' ? 'DRAWER_STEPPED' : displayForm;
      openQuestionnaireDrawer(btn, effForm).catch((e) => {
        console.warn('[ai-home] open questionnaire drawer (from pre-card) failed', e);
        showToast('问卷加载失败，请重试', 'fail');
      });
    },
    [funcButtons],
  );

  // [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 打开通用问卷抽屉：调 render-meta 拿模板与题目
  // [PRD-HSC-OPTIM-V3 2026-05-21] Bug1 修复：进入抽屉前强制再拉一次 render-meta（即便按钮列表已有缓存），
  //   并把 auto_next_enabled / questions_per_page / presentation_container 三个字段
  //   用最新值"覆盖"到 qnDrawerButton，避免使用「按钮列表接口」的老数据。
  const openQuestionnaireDrawer = useCallback(
    async (btn: FunctionButton, displayForm: QnDisplayForm) => {
      setQnDrawerButton(btn);
      setQnDrawerDisplayForm(displayForm);
      setQnDrawerLoading(true);
      setQnDrawerOpen(true);
      try {
        const meta = await api.get<any>(`/api/questionnaire/buttons/${btn.id}/render-meta`);
        if (meta?.template) {
          setQnDrawerTemplate(meta.template as QnTemplate);
          setQnDrawerQuestions((meta.questions || []) as QnQuestion[]);
          // 用 render-meta 返回的最新呈现配置覆盖按钮对象（顶层 + button 节点都覆盖一遍兜底）
          const mergedBtn: any = { ...btn };
          if (meta?.button) {
            mergedBtn.auto_next_enabled = !!meta.button.auto_next_enabled;
            mergedBtn.questions_per_page = Number(meta.button.questions_per_page || 1);
            mergedBtn.presentation_container = meta.button.presentation_container || 'DRAWER';
            mergedBtn.result_cta = meta.result_cta ?? mergedBtn.result_cta ?? null;
          } else {
            mergedBtn.auto_next_enabled = !!meta.auto_next_enabled;
            mergedBtn.questions_per_page = Number(meta.questions_per_page || 1);
            mergedBtn.presentation_container = meta.presentation_container || 'DRAWER';
          }
          // 顶层 result_cta 也透传一份（详情页可直接消费）
          mergedBtn.result_cta = meta?.result_cta ?? mergedBtn.result_cta ?? null;
          setQnDrawerButton(mergedBtn);
          // [BUG-HSC-V31 2026-05-21] Bug1 真正根因修复：
          //   当后台开启「自动下一步」+「每页 1 题」时，必须升级到 DRAWER_STEPPED 一题一屏模式，
          //   因为 autoNext 逻辑仅在 stepped 模式生效（DRAWER_SCROLL 一屏多题模式无 autoNext）。
          //   之前 displayForm 直接取自按钮配置，常常落到 DRAWER_SCROLL，导致 autoNext 形同虚设。
          try {
            const _autoNext = !!mergedBtn.auto_next_enabled;
            const _perPage = Number(mergedBtn.questions_per_page || 1);
            if (_autoNext && _perPage === 1) {
              setQnDrawerDisplayForm('DRAWER_STEPPED');
              if (typeof console !== 'undefined') {
                // eslint-disable-next-line no-console
                console.debug('[ai-home] force DRAWER_STEPPED due to autoNext+per_page=1');
              }
            }
          } catch {
            // 忽略
          }
          if (typeof console !== 'undefined') {
            // eslint-disable-next-line no-console
            console.debug('[ai-home] render-meta merged', {
              btn_id: btn.id,
              auto_next_enabled: mergedBtn.auto_next_enabled,
              questions_per_page: mergedBtn.questions_per_page,
              container: mergedBtn.presentation_container,
            });
          }
        } else {
          showToast('问卷模板未配置，请联系运营', 'warning');
          setQnDrawerOpen(false);
        }
      } catch (e: any) {
        console.warn('[ai-home] render-meta fetch failed', e);
        showToast('问卷加载失败，请重试', 'fail');
        setQnDrawerOpen(false);
      } finally {
        setQnDrawerLoading(false);
      }
    },
    [],
  );

  // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 通用问卷抽屉提交 —— 统一消费后端 chat_messages 协议
  //
  // 修复以下 3 个 Bug：
  //   Bug-1：AI 追问位置错 → 强制按 card → text → followup_chips 顺序注入
  //   Bug-2：总结消息身份发错 + 占位符未渲染 → 全部 sender=ai；占位符在后端渲染
  //   Bug-3：结果汇总卡片缺失 → AI 侧 questionnaire_result_card 包含主体质 + 雷达 + 查看详情
  const handleQuestionnaireDrawerSubmit = useCallback(
    async (items: QnSubmitAnswerItem[]) => {
      const btn = qnDrawerButton;
      const tpl = qnDrawerTemplate;
      if (!btn || !tpl) return;
      try {
        // [BUG-HSC-V31 2026-05-21] B-2 修复：必须把 subject_* 4 字段从胶囊上下文塞到 payload，
        // 否则后端只能按 consultant_id 反查兜底，老/虚拟成员场景下会丢 name/relation，
        // 详情页就会回落到"本人"。
        // 注意：selectedConsultant 也可能是"本人成员"（is_self=true），此时按 self 处理。
        const _isFamily = !!selectedConsultant && !selectedConsultant.is_self;
        const _subjectKind: 'self' | 'family' = _isFamily ? 'family' : 'self';
        const _subjectName: string | null = _isFamily
          ? (selectedConsultant?.nickname || null)
          : null;
        const _subjectRelation: string | null = _isFamily
          ? ((selectedConsultant?.relation_type_name as string | undefined) ||
              (selectedConsultant?.relationship_type as string | undefined) ||
              null)
          : null;
        const resp = await api.post<any>('/api/questionnaire/submit', {
          template_id: tpl.id,
          consultant_id: selectedConsultant?.id ?? null,
          answers: items,
          subject_kind: _subjectKind,
          subject_member_id: selectedConsultant?.id ?? null,
          subject_name: _subjectName,
          subject_relation: _subjectRelation,
        });
        setQnDrawerOpen(false);
        const card = (resp?.card || { fields: [] }) as QnResultCardPayload;
        // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 优先消费后端的 chat_messages 序列
        const chatMessages: Array<any> = Array.isArray(resp?.chat_messages) ? resp.chat_messages : [];
        const newMsgs: ChatMessage[] = [];
        const baseTs = Date.now();
        const universalCard = resp?.result_card_payload || null;
        if (chatMessages.length > 0) {
          chatMessages.forEach((m: any, idx: number) => {
            // 严格执行协议：所有消息 sender=ai
            if (m.type === 'questionnaire_result_card') {
              newMsgs.push({
                id: `qn-card-${baseTs}-${idx}`,
                role: 'assistant',
                content: '',
                time: new Date().toISOString(),
                kind: 'questionnaire_result_card',
                questionnaireResult: {
                  answerId: resp.answer_id,
                  templateId: tpl.id,
                  buttonId: Number(btn.id),
                  card,
                  aiStatusText: null,
                  universalCard: m.card || universalCard,
                },
              });
            } else if (m.type === 'text') {
              newMsgs.push({
                id: `qn-text-${baseTs}-${idx}`,
                role: 'assistant',
                content: m.text || '',
                time: new Date().toISOString(),
                kind: 'text',
              });
            } else if (m.type === 'followup_chips') {
              newMsgs.push({
                id: `qn-chips-${baseTs}-${idx}`,
                role: 'assistant',
                content: '',
                time: new Date().toISOString(),
                kind: 'followup_chips',
                followupChips: {
                  chips: Array.isArray(m.chips) ? m.chips : [],
                  questionnaireResultId: m?.render_meta?.questionnaire_result_id || resp.answer_id,
                  templateCode: m?.render_meta?.template_code || tpl.code,
                  disabled: false,
                },
              });
            }
          });
        } else {
          // 兜底：旧版后端无 chat_messages 时仍以单卡片渲染（也强制 AI 侧）
          newMsgs.push({
            id: `qn-card-${baseTs}`,
            role: 'assistant',
            content: '',
            time: new Date().toISOString(),
            kind: 'questionnaire_result_card',
            questionnaireResult: {
              answerId: resp.answer_id,
              templateId: tpl.id,
              buttonId: Number(btn.id),
              card,
              aiStatusText: null,
              universalCard,
            },
          });
        }

        // [PRD-TAG-RECOMMEND-V1 2026-05-20] 推荐卡片插入到 text 之前 / chips 之前
        const recommendGoods: RecommendGoodsItem[] = Array.isArray(resp?.recommend_goods)
          ? resp.recommend_goods
          : [];
        const recommendClickMode: 'drawer' | 'external' =
          resp?.recommend_click_mode === 'external' ? 'external' : 'drawer';
        const resultDisplayMode: string = resp?.result_display_mode || 'simple';
        if (resultDisplayMode === 'triple' && recommendGoods.length > 0) {
          // 紧跟卡片之后、text 之前
          const insertIdx = newMsgs.findIndex((x) => x.kind === 'text');
          const recMsg: ChatMessage = {
            id: `qn-rec-${baseTs}`,
            role: 'assistant',
            content: '',
            time: new Date().toISOString(),
            kind: 'questionnaire_recommend_card',
            questionnaireRecommend: {
              goods: recommendGoods,
              clickMode: recommendClickMode,
            },
          };
          if (insertIdx < 0) {
            newMsgs.push(recMsg);
          } else {
            newMsgs.splice(insertIdx, 0, recMsg);
          }
        }

        setMessages((prev) => [...prev, ...newMsgs]);
        lastMsgTimeRef.current = Date.now();
        // ⚠️ 不再调用 handleSend(aiContext, 'preset') —— 该路径会生成"用户身份的摘要消息 + 占位符"
        // 这是 Bug-2 的根本来源（身份发错 + 占位符未渲染）。新协议中所有 AI 侧消息已由后端
        // chat_messages 完整提供，前端无需再触发额外的"AI 解读"流式回复。
      } catch (e: any) {
        console.warn('[ai-home] qn submit failed', e);
        showToast(e?.response?.data?.detail || '问卷提交失败', 'fail');
      }
    },
    [qnDrawerButton, qnDrawerTemplate, selectedConsultant],
  );

  // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查抽屉提交：插入卡片气泡 → 调用后端 start → 插入 AI 回答
  // [PRD-HSC-SSE 2026-05-16] 改造为 SSE 流式：调用 /api/health-self-check/start-stream，
  //   按 event(meta|delta|done) 增量更新 AI 气泡内容；同时把 symptom_description 透传给后端 + 卡片展示。
  const handleHealthSelfCheckSubmit = useCallback(
    async (payload: HealthSelfCheckSubmitPayload, _template: HealthCheckTemplateDetail) => {
      setHscDrawerOpen(false);
      const cardMsg: ChatMessage = {
        id: `hsc-${Date.now()}`,
        role: 'user',
        content: '',
        time: new Date().toISOString(),
        kind: 'health_self_check_card',
        healthSelfCheck: {
          archiveId: payload.archive_id ?? null,
          archiveName: payload.archive_name,
          archiveAge: payload.archive_age ?? null,
          archiveGender: payload.archive_gender ?? null,
          bodyPart: payload.body_part,
          symptoms: payload.symptoms,
          duration: payload.duration,
          templateId: payload.template_id,
          buttonId: payload.button_id,
          symptomDescription: payload.symptom_description,
        },
      };
      const aiPlaceholder: ChatMessage = {
        id: `a-hsc-${Date.now()}`,
        role: 'assistant',
        content: '正在分析中…',
        time: new Date().toISOString(),
        isStreaming: true,
      };
      setMessages((prev) => prev.concat(cardMsg, aiPlaceholder));

      // [BUG-FIX 2026-05-16] 后端 schema 要求 body_part_id（整数），
      // 不接受 archive_name/archive_age/archive_gender/body_part 对象。
      // 展示模型（卡片气泡）仍保留完整 body_part 对象，但发给后端的 payload 只传 body_part_id。
      const requestBody = {
        template_id: payload.template_id,
        button_id: payload.button_id,
        archive_id: payload.archive_id ?? null,
        body_part_id: payload.body_part?.id,
        symptoms: payload.symptoms,
        duration: payload.duration,
        symptom_description: payload.symptom_description ?? null,
      };

      // 组装 SSE 流式请求所需的 URL + Header。
      // base URL 与 axios 实例保持一致（next.config 的 basePath，例如线上 /autodev/<uuid>）。
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
      const sseUrl = `${basePath}/api/health-self-check/start-stream`;
      // token 与 api.ts 拦截器保持一致：C 端顾客域使用 'token'
      let token: string | null = null;
      try {
        token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
      } catch {
        token = null;
      }
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        // 与 api.ts 一致：C 端顾客域客户端类型
        'Client-Type': 'h5-user',
        'X-Client-Type': 'h5-user',
        'X-Client-Source': 'h5-customer',
      };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      // SSE 事件流解析：按 \n\n 拆 event，每个 event 内部 `event: <type>\ndata: <json>`
      let buffer = '';
      let accumulated = '';
      let finalized = false;
      const applyDelta = (chunkText: string) => {
        accumulated += chunkText;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiPlaceholder.id ? { ...m, content: accumulated, isStreaming: true } : m,
          ),
        );
      };
      const finalize = (fullText: string) => {
        finalized = true;
        const text = (fullText || accumulated || '').trim() || '分析完成';
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiPlaceholder.id ? { ...m, content: text, isStreaming: false } : m,
          ),
        );
      };
      const handleEventBlock = (block: string) => {
        // 每个 event block 可能形如:
        // event: meta\ndata: {...}
        // event: delta\ndata: {...}
        // event: done\ndata: {...}
        const lines = block.split('\n');
        let eventType = '';
        const dataLines: string[] = [];
        for (const ln of lines) {
          if (ln.startsWith('event:')) {
            eventType = ln.slice(6).trim();
          } else if (ln.startsWith('data:')) {
            dataLines.push(ln.slice(5).replace(/^\s/, ''));
          }
        }
        const dataStr = dataLines.join('\n');
        if (!eventType || !dataStr) return;
        let dataObj: any = null;
        try {
          dataObj = JSON.parse(dataStr);
        } catch {
          return;
        }
        if (eventType === 'meta') {
          // 可记录 session_id / user_message_id / card_payload，前端卡片已渲染无需强制使用
          return;
        }
        if (eventType === 'delta') {
          const c = typeof dataObj?.content === 'string' ? dataObj.content : '';
          if (c) applyDelta(c);
          return;
        }
        if (eventType === 'done') {
          const full = typeof dataObj?.full_content === 'string' ? dataObj.full_content : '';
          finalize(full);
          return;
        }
      };

      try {
        const resp = await fetch(sseUrl, {
          method: 'POST',
          headers,
          body: JSON.stringify(requestBody),
        });
        if (!resp.ok || !resp.body) {
          throw new Error(`SSE HTTP ${resp.status}`);
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder('utf-8');
        // 首条 delta 之前先把占位文案清空
        accumulated = '';
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiPlaceholder.id ? { ...m, content: '', isStreaming: true } : m,
          ),
        );
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          // SSE event 之间以两个换行分隔
          let sepIdx = buffer.indexOf('\n\n');
          while (sepIdx !== -1) {
            const rawBlock = buffer.slice(0, sepIdx);
            buffer = buffer.slice(sepIdx + 2);
            if (rawBlock.trim()) handleEventBlock(rawBlock);
            sepIdx = buffer.indexOf('\n\n');
          }
        }
        // flush 剩余 buffer
        if (buffer.trim()) {
          handleEventBlock(buffer);
          buffer = '';
        }
        if (!finalized) {
          // 没有收到 done 事件兜底：直接以累计内容定型
          finalize(accumulated);
        }
      } catch {
        if (!finalized) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiPlaceholder.id
                ? { ...m, content: '分析失败，请点击重试', isStreaming: false }
                : m,
            ),
          );
        }
      }
    },
    [],
  );

  const handleFuncButton = (btn: FunctionButton) => {
    const key = btn.button_type || String(btn.id);
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

  /**
   * [AICHAT-OPTIM-FIX-V1 F-06/F-07] 功能按钮点击调度器（数据源：chat_function_buttons）
   * 根据 button_type 调用 resolveCardType 决定行为：
   *  - quick_ask → 直接以 preset_prompt 作为用户消息发送（首页就地处理）
   *  - navigate(external_link) → external_url 跳转
   *  - upload / sdk_call / navigate(其它) → 把卡片消息插入对话流（AI 气泡，含 ChatCard）
   * 同时上报曝光埋点 + 在执行 auto_user_message 时同步插入用户消息
   */
  const handleFunctionButtonClick = (btn: FunctionButton) => {
    try {
      // [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 通用问卷分发（最高优先级）
      // 当 ai_function_type=questionnaire 时，按 questionnaire_display_form 决定行为：
      //   DRAWER_SCROLL  → 弹通用问卷抽屉（一屏多题）
      //   DRAWER_STEPPED → 弹通用问卷抽屉（一题一屏）
      //   INLINE_CHAT    → 在对话流中插入问卷气泡（轻量级）—— 复用现有 ai-chat-card 走原流程
      // [PRD-TCM-DRAWER-V12-BUG3 2026-05-20] 当按钮配置为问卷类型但未保存 template_id 时
      // （通常因 Bug 1 加载问卷模板失败导致运营未能选模板），显式提示运营，避免点击静默无反应
      if (
        btn.button_type === 'ai_function' &&
        btn.ai_function_type === 'questionnaire' &&
        !btn.questionnaire_template_id
      ) {
        showToast('该功能按钮未关联问卷模板，请联系管理员前往「功能按钮管理」补充配置', 'warning');
        return;
      }
      if (
        btn.button_type === 'ai_function' &&
        btn.ai_function_type === 'questionnaire' &&
        btn.questionnaire_template_id
      ) {
        const displayForm = (btn.questionnaire_display_form || 'DRAWER_SCROLL') as QnDisplayForm;
        if (displayForm === 'DRAWER_SCROLL' || displayForm === 'DRAWER_STEPPED') {
          // [PRD-TCM-DRAWER-V12 2026-05-20] 若 pre_card_enabled 则先弹"对话内说明卡片"，再由用户点击进抽屉
          const preCardEnabled = btn.pre_card_enabled !== false;
          if (preCardEnabled) {
            insertQuestionnairePreCardMessages(btn);
            return;
          }
          openQuestionnaireDrawer(btn, displayForm).catch((e) => {
            console.warn('[ai-home] open questionnaire drawer failed', e);
            showToast('问卷加载失败，请重试', 'fail');
          });
          return;
        }
        // [PRD-TCM-DRAWER-V12 2026-05-20] INLINE_CHAT 形态：插入对话内说明卡片（用户气泡 + AI 气泡卡片）
        if (displayForm === 'INLINE_CHAT') {
          insertQuestionnairePreCardMessages(btn);
          return;
        }
      }

      // [BUG-FIX 2026-05-16] health_self_check 类型：与胶囊行为完全一致，直接弹出健康自查抽屉
      // 修复前：宫格分发漏掉本分支，落入兜底逻辑被当成"导航卡片"渲染，导致点击无反应
      // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 兼容新主类型 ai_function + ai_function_type=health_self_check
      // ⚠️ [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] DEPRECATED：老 health_self_check 子类型分支保留
      //    仅当按钮还没被数据迁移升级时进入；新按钮一律走上面的 questionnaire 分支。
      const isHealthSelfCheck = btn.button_type === 'health_self_check' ||
        (btn.button_type === 'ai_function' && btn.ai_function_type === 'health_self_check');
      if (isHealthSelfCheck) {
        const strategy = btn.archive_missing_strategy || 'use_default';
        if (!selectedConsultant && strategy === 'force_toast') {
          showToast('请先在顶部选择咨询档案', 'warning');
          return;
        }
        setHscDrawerButton(btn);
        setHscDrawerPrefill(null);
        setHscDrawerOpen(true);
        return;
      }

      // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] page_navigate 主类型：按 pre_card_for_navigate 决定行为
      //   - 开关关闭（默认）：直接跳转 external_url（保持原行为）
      //   - 开关开启：先弹卡片，让用户点卡片按钮再跳转（详见下方 navigate 卡片渲染）
      if (btn.button_type === 'page_navigate' && !btn.pre_card_for_navigate) {
        let url = (btn.external_url || '').trim();
        // [PRD-AI-HOME-V1 2026-05-19] 旧 (tabs) 路径运行时兜底：
        //   将 `/(tabs)/services` `/tabs/services` 等改写为独立 `/services`，避免 DB 脏数据导致 404。
        const legacyFixed = url.replace(/^\/?\(tabs\)/, '').replace(/^\/?tabs\//, '/');
        if (legacyFixed !== url) {
          if (typeof console !== 'undefined') console.warn('[ai-home func btn] legacy (tabs) path rewritten:', url, '->', legacyFixed);
          url = legacyFixed;
        }
        if (url.startsWith('http')) {
          window.location.href = url;
          return;
        } else if (url.startsWith('/') || url.startsWith('pages/')) {
          router.push(url.startsWith('/') ? url : `/${url}`);
          return;
        }
        // [PRD-PAGE-NAVIGATE-EXTERNAL-URL-FIX-V1 2026-05-19] Bug 修复 F3：
        // page_navigate + 先弹卡片=否 + external_url 为空（异常 / 历史脏数据），
        // 不再走"把 auto_user_message / 按钮名作为用户消息发出"的兜底（防止污染对话区），
        // 改为给用户一条明确提示，并打前端日志埋点 page_navigate_empty_url。
        try {
          if (typeof console !== 'undefined') {
            console.warn('[ai-home func btn] page_navigate_empty_url', { id: btn.id, name: btn.name });
          }
          try { aiHomeFnTrack.cardFail(btn.id, 'page_navigate_empty_url'); } catch {}
          showToast('该按钮跳转地址异常，请联系管理员', 'warning');
        } catch {}
        return;
      }

      const cardType: ChatCardType = resolveCardType(btn.button_type, btn.ai_function_type);

      // quick_ask 类型：直接以 preset_prompt（或 auto_user_message）作为用户消息发送
      if (cardType === 'quick_ask') {
        const presetText = (btn.preset_prompt || btn.auto_user_message || btn.name || '').trim();
        if (presetText) {
          lastMsgTimeRef.current = Date.now();
          handleSend(presetText, 'preset');
        }
        return;
      }

      // 老 navigate 类型 + external_url 存在：直接跳转（兼容老枚举）
      if (cardType === 'navigate' && btn.button_type !== 'page_navigate' &&
          btn.button_type !== 'ai_function' && btn.external_url) {
        const url = btn.external_url.trim();
        if (url.startsWith('http')) {
          window.location.href = url;
          return;
        } else if (url.startsWith('/')) {
          router.push(url);
          return;
        }
      }

      // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] AI 开场白：如果按钮配置了 ai_opening，
      // 在弹卡片之前先在对话区插入一条 AI 文本气泡（assistant 角色）
      const aiOpening = (btn.ai_opening || '').trim();
      if (aiOpening) {
        const openingMsg: ChatMessage = {
          id: `opening-${Date.now()}-${btn.id}`,
          role: 'assistant',
          content: aiOpening,
          time: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, openingMsg]);
      }

      // 其余情况（upload / sdk_call / navigate 无 url 或 page_navigate+开关开）→ 在对话流插入卡片消息
      const cardContent = JSON.stringify({
        kind: 'ai-chat-card',
        cardType,
        button: backendButtonToCardButton({
          id: btn.id,
          name: btn.name,
          icon: btn.icon,
          icon_url: btn.icon_url,
          button_type: btn.button_type,
          prompt_template_id: btn.prompt_template_id,
          external_url: btn.external_url,
          preset_prompt: btn.preset_prompt,
          auto_user_message: btn.auto_user_message,
          card_title: btn.card_title,
          card_subtitle: btn.card_subtitle,
          card_cover_image: btn.card_cover_image,
          button_sub_desc: btn.button_sub_desc,
          // [PRD-AICHAT-FUNCBTN-OPTIM-V1] 新字段透传
          ai_function_type: btn.ai_function_type,
          ai_opening: btn.ai_opening,
          pre_card_for_navigate: btn.pre_card_for_navigate,
          capture_purpose: btn.capture_purpose,
        }),
      });
      const cardMsg: ChatMessage = {
        id: `card-${Date.now()}-${btn.id}`,
        role: 'assistant',
        content: cardContent,
        time: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, cardMsg]);
      try { aiHomeFnTrack.cardExposure(btn.id, cardType); } catch {}
    } catch (e: any) {
      try { aiHomeFnTrack.cardFail(btn.id, String(e?.message || 'click-error')); } catch {}
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
      showToast('当前浏览器不支持语音输入', 'fail');
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
          showToast('录音时间太短', 'warning');
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
            showToast('未识别到语音内容，请重试', 'warning');
          }
        } catch {
          Toast.clear();
          showToast('语音识别失败，请重试', 'fail');
        }
      };

      recorder.start(250);
      setRecording(true);
      setRecordCancelled(false);
    } catch {
      showToast('无法访问麦克风，请检查权限设置', 'fail');
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
    showToast('已取消');
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
            showToast('播放失败，请重试', 'fail');
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
          showToast('当前浏览器不支持语音播报', 'fail');
          };
        audio.play();
        return;
      }
    } catch {}
    setTtsPlaying(false);
    showToast('当前浏览器不支持语音播报', 'fail');
  };

  // [PRD-440] 复制反馈：Web 端顶部 Toast「已复制」/ 移动端调用系统原生轻提示
  const handleCopy = (text: string) => {
    navigator.clipboard?.writeText(text).then(() => {
      notifyCopied();
    }).catch(() => {
      showToast('复制失败', 'fail');
    });
  };

  const handleNewConversation = useCallback(() => {
    // [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 「+ 新对话」按钮：
    // - 当前 active 会话为空（message_count===0） → Toast「当前已是新对话」，不重复创建
    // - 当前 active 会话有消息 → 调用 /archive 真正归档，然后清空对话区回到欢迎页
    const curSid = currentSidRef.current;
    const hasMessages = messages.length > 0;
    if (!hasMessages) {
      showToast('当前已是新对话');
      return;
    }
    // 异步归档旧会话（失败不阻塞前端动作）
    if (curSid) {
      try {
        api.post(`/api/chat-sessions/${curSid}/archive`).catch(() => {});
      } catch {
        /* ignore */
      }
    }
    setMessages([]);
    currentSidRef.current = null;
    setSessionId(null);
    setLastMsgTime(0);
    // 倒计时重置：未进入新会话前不计时
    lastAiDoneAtRef.current = 0;
    // [BUG_FIX_AI_HOME_3BUGS_20260517 · Bug C]
    // 新建会话时强制把咨询人重置为「本人」，避免上一轮 X 的状态被带过来：
    // 旧实现：胶囊已显示"本人"但 selectedConsultant 仍是 X，AI 回答按 X 档案给建议。
    // 修复：胶囊 / 发送参数 / 档案引用 全部从同一个 state 读取，保证三处一致。
    setSelectedConsultant(null);
    abortRef.current?.abort();
    // [BUG-466] 主动开新会话也通知抽屉刷新，让原会话立刻"沉"到历史列表里
    try {
      window.dispatchEvent(new Event('bh-history-refresh'));
    } catch {
      /* ignore */
    }
  }, [messages.length, setLastMsgTime]);

  /**
   * [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 空闲超时自动归档检查
   *
   * 条件：
   *   - 有活跃会话（currentSidRef.current 非空）
   *   - 有 lastAiDoneAt（即 AI 已完整回复至少一次）
   *   - 流式未在进行（messages 没有 isStreaming）
   *   - Date.now() - lastAiDoneAt >= idleTimeout
   *
   * 动作：调用 /archive → 清空对话区 → 回到欢迎页 → 通知抽屉刷新
   */
  const idleArchiveCheck = useCallback(() => {
    const curSid = currentSidRef.current;
    const lastDone = lastAiDoneAtRef.current;
    if (!curSid || !lastDone) return;
    // 流式中不归档（PRD §6.1.1）
    try {
      if (messages.some((m: any) => m.isStreaming)) return;
    } catch {
      /* ignore */
    }
    // [PRD-AI-HOME-OPTIM-V4 F-切人-03] 撤销期内（5 秒内）暂停 60 分钟计时
    if (refreshPaused) return;
    if (Date.now() - lastDone < idleTimeout) return;

    // 触发自动归档
    try {
      api.post(`/api/chat-sessions/${curSid}/archive`).catch(() => {});
    } catch {
      /* ignore */
    }
    setMessages([]);
    currentSidRef.current = null;
    setSessionId(null);
    setLastMsgTime(0);
    lastAiDoneAtRef.current = 0;
    try {
      window.dispatchEvent(new Event('bh-history-refresh'));
    } catch {
      /* ignore */
    }
  }, [idleTimeout, messages, setLastMsgTime, refreshPaused]);

  // [PRD-AI-HOME-OPTIM-V4 F-刷新-04] 进入时机全端覆盖：
  //   - 5 分钟轮询（既有）
  //   - visibilitychange（既有）
  //   - pageshow（含 bfcache 回退；浏览器后退/前进时恢复页面）
  //   - focus（窗口聚焦）
  // 任何一个时机被触发 → 立即调用 idleArchiveCheck，保证 60min 阈值过线后第一时间清空旧会话
  useEffect(() => {
    const POLL_INTERVAL = 5 * 60 * 1000;
    const timer = setInterval(idleArchiveCheck, POLL_INTERVAL);
    const onVisibility = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
        // 切回前台立即检查一次（避免长时间后台导致定时器停摆）
        idleArchiveCheck();
      }
    };
    const onPageShow = (_e: PageTransitionEvent) => {
      // pageshow 含 bfcache 回退（persisted=true）；都需要立即复检
      idleArchiveCheck();
    };
    const onFocus = () => {
      idleArchiveCheck();
    };
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibility);
    }
    if (typeof window !== 'undefined') {
      window.addEventListener('pageshow', onPageShow);
      window.addEventListener('focus', onFocus);
    }
    return () => {
      clearInterval(timer);
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisibility);
      }
      if (typeof window !== 'undefined') {
        window.removeEventListener('pageshow', onPageShow);
        window.removeEventListener('focus', onFocus);
      }
    };
  }, [idleArchiveCheck]);

  // [PRD-AI-HOME-OPTIM-V4 M3 · F-悬浮-02] 首次进入展示引导气泡（3 秒消失，仅一次）
  // 使用 localStorage 'aihome_v4_floating_ball_guide_shown' 标记，已展示过的用户不再展示
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const STORAGE_KEY = 'aihome_v4_floating_ball_guide_shown';
    try {
      const shown = window.localStorage.getItem(STORAGE_KEY);
      if (shown === '1') return;
    } catch {
      return;
    }
    // 延迟 800ms 出现（让首屏先稳定）
    const showTimer = setTimeout(() => {
      setFloatingFirstGuideVisible(true);
      try {
        api.post('/api/ai-home/track', {
          event: 'first_guide_shown',
          platform: 'h5',
          payload: {},
        }).catch(() => {});
      } catch {}
      // 3 秒后自动消失，并记录已展示
      const hideTimer = setTimeout(() => {
        setFloatingFirstGuideVisible(false);
        try {
          window.localStorage.setItem(STORAGE_KEY, '1');
        } catch {}
      }, 3000);
      // 把 hideTimer 也保存以便清理
      (showTimer as any)._hide = hideTimer;
    }, 800);
    return () => {
      clearTimeout(showTimer);
      const ht = (showTimer as any)?._hide;
      if (ht) clearTimeout(ht);
    };
  }, []);

  // [PRD-AI-HOME-OPTIM-V4 M3 · F-悬浮-03] 点击悬浮球：展开/收起面板
  const handleFloatingBallClick = useCallback(() => {
    setFloatingPanelOpen((prev) => {
      const next = !prev;
      if (next) {
        try {
          api.post('/api/ai-home/track', {
            event: 'floating_ball_clicked',
            platform: 'h5',
            payload: {
              session_minutes: lastMsgTime ? Math.round((Date.now() - lastMsgTime) / 60000) : 0,
            },
          }).catch(() => {});
        } catch {}
      }
      return next;
    });
    // 点击悬浮球同时关掉首次引导气泡
    setFloatingFirstGuideVisible(false);
  }, [lastMsgTime]);

  // [PRD-AI-HOME-OPTIM-V4 F-刷新-05] 进入页面拉取最新刷新阈值（后端 settings.SESSION_REFRESH_MINUTES）
  // 失败静默：使用既有默认值 60min
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res: any = await api.get('/api/ai-home/refresh-config');
        const data = res?.data ?? res;
        const ms = typeof data?.session_refresh_ms === 'number' && data.session_refresh_ms > 0
          ? data.session_refresh_ms
          : (typeof data?.session_refresh_minutes === 'number' && data.session_refresh_minutes > 0
            ? data.session_refresh_minutes * 60 * 1000
            : null);
        if (!cancelled && ms && ms !== idleTimeout) {
          setIdleTimeout(ms);
        }
      } catch {
        // 静默
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // [PRD-420 F5 / BUG-466 (2026-05-11)] 切换咨询对象后的会话处理
  // 总策略：自动新建会话 + 用户体验增强（含 5 秒「返回上一会话」撤销栈）
  //
  // BUG-466 修复要点：
  // 1. 切换"瞬间"先把 currentSidRef.current = null，立刻屏蔽旧 sid 的可用性，
  //    防止极速操作（切换同一帧按发送）把消息串到旧会话上（根因 C）
  // 2. 调用合并版后端接口 `POST /api/chat-sessions`，
  //    携带 archive_previous_session_id 一次完成"归档旧会话 + 创建新会话"（根因 D）
  // 3. 拿到新 sid 后立刻 currentSidRef.current = newSid → setSessionId(newSid)（ref 永远先行）
  // 4. 派发 `bh-history-refresh` 事件，让左侧抽屉重新拉取列表（根因 A）
  //    确保"原会话被归档到顶部 + 新会话作为占位条目"两条记录立刻可见
  // 5. 撤销时同样派发 bh-history-refresh，让抽屉同步回滚显示
  const handleConsultantSelect = useCallback(async (member: FamilyMemberItem | null) => {
    // 静默打断当前流式响应
    abortRef.current?.abort();

    const prevSessionId = currentSidRef.current;
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

    // [BUG-466 关键修复] 切换瞬间立刻屏蔽旧 sid，防止 await 期间用户极速发送
    // 时 handleSend / checkIdleAndMaybeNewSession 闭包仍读到旧 sid。
    currentSidRef.current = null;
    setSessionId(null);
    setMessages([]);
    setLastMsgTime(0);

    // [BUG-466] 合并版接口：一次请求完成"归档旧会话 + 创建新会话"
    // 优先使用 /api/chat-sessions（支持 archive_previous_session_id），
    // 失败 / 该接口不可用时退化为单独的 createChatSession（保持向后兼容）。
    let newSid: string | null = null;
    try {
      const tryRes: any = await api.post('/api/chat-sessions', {
        session_type: 'health_qa',
        family_member_id: member ? member.id : null,
        archive_previous_session_id:
          prevSessionId !== null && prevSessionId !== undefined
            ? Number(prevSessionId)
            : null,
      });
      const data = tryRes?.data ?? tryRes;
      const id = data?.id;
      if (id !== undefined && id !== null) {
        newSid = String(id);
      }
    } catch {
      // 合并接口失败，退化为旧路径
      newSid = null;
    }

    if (!newSid) {
      const res = await createChatSession({
        session_type: 'health_qa',
        family_member_id: member ? member.id : undefined,
      });
      newSid = res.ok ? res.sessionId : null;
    }

    if (newSid) {
      // ref 永远领先 state，保证后续即便 React 还未提交 state，也能读到新 sid
      currentSidRef.current = newSid;
      setSessionId(newSid);
    }

    // [PRD-AI-HOME-OPTIM-V4 M2 · F-切人-02] 系统消息气泡：永久留痕
    // 在新会话第一条系统消息（在 AI 欢迎语之前），文案"—— 现在开始为 妈妈 提供健康咨询 ——"
    const systemMsg: ChatMessage = {
      id: `sys-switch-${Date.now()}`,
      role: 'assistant',
      content: `—— 现在开始为 ${targetName} 提供健康咨询 ——`,
      time: new Date().toISOString(),
      // 自定义标记：消息类型为系统切换通知
      kind: 'system_switch_notice' as any,
    } as any;
    setMessages([systemMsg]);

    // [BUG-466 根因 A 修复] 派发 history 刷新事件，
    // 左侧抽屉 Sidebar 监听到后会立刻重新拉取 /api/chat-sessions 列表，
    // 让原会话被归档到顶部 + 新会话作为占位条目立刻可见。
    try {
      window.dispatchEvent(new Event('bh-history-refresh'));
    } catch {
      /* ignore */
    }

    // [PRD-AI-HOME-OPTIM-V4 M2 · F-切人-01] Toast 浮层（中央偏上，2 秒消失）
    setCenterToastText(`已切换为 ${targetName} 咨询`);
    setCenterToastVisible(true);
    if (centerToastTimerRef.current) clearTimeout(centerToastTimerRef.current);
    centerToastTimerRef.current = setTimeout(() => {
      setCenterToastVisible(false);
    }, 2000);

    // [M1] 蓝色横条撤销功能已移除，不再设置 undoSnapshot / undoToastVisible

    // 切换咨询人埋点
    try {
      api.post('/api/ai-home/track', {
        event: 'switch_consultant',
        platform: 'h5',
        payload: {
          from_id: prevConsultant?.id ?? null,
          to_id: member?.id ?? null,
          relation: relationLabel,
        },
      }).catch(() => {});
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedConsultant, messages]);

  // [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18 / F4]
  // 消息列表或咨询人切换时，批量刷新所有识药卡片的「是否已加入用药计划」状态
  useEffect(() => {
    const names: string[] = [];
    for (const m of messages) {
      if (
        m.drugMeta &&
        m.drugMeta.message_type === 'drug_identify_card' &&
        Array.isArray(m.drugMeta.medicines)
      ) {
        const n =
          m.drugMeta.medicines[0]?.name ||
          m.drugMeta.medicines[0]?.brand ||
          '';
        if (n) names.push(n);
      }
    }
    if (names.length > 0) {
      refreshDrugAddedStatus(names);
    }
  }, [messages, selectedConsultant, refreshDrugAddedStatus]);

  // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F1~F3] 监听 messages，对新到达的识药卡按 800/1600/2400ms 渐进释放
  useEffect(() => {
    for (const m of messages) {
      if (
        m.drugMeta &&
        m.drugMeta.message_type === 'drug_identify_card' &&
        !_drugCardProgressiveCache.has(m.id) &&
        !drugCardVisibleSectionsMap[m.id]
      ) {
        const mid = m.id;
        // 初始：仅基础信息可见
        setDrugCardVisibleSectionsMap((prev) => ({
          ...prev,
          [mid]: { basic: true, usage: false, safety: false, risk: false },
        }));
        // 依次释放
        setTimeout(() => {
          setDrugCardVisibleSectionsMap((prev) => ({
            ...prev,
            [mid]: { ...(prev[mid] || { basic: true, usage: false, safety: false, risk: false }), usage: true },
          }));
        }, 800);
        setTimeout(() => {
          setDrugCardVisibleSectionsMap((prev) => ({
            ...prev,
            [mid]: { ...(prev[mid] || { basic: true, usage: true, safety: false, risk: false }), safety: true },
          }));
        }, 1600);
        setTimeout(() => {
          setDrugCardVisibleSectionsMap((prev) => ({
            ...prev,
            [mid]: { basic: true, usage: true, safety: true, risk: true },
          }));
          _drugCardProgressiveCache.add(mid);
        }, 2400);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages]);

  // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F10 2026-05-18]
  // 刷新当前咨询人维度的「用药提醒」红点 + 空状态
  const refreshReminderRedDot = useCallback(async () => {
    const cid = selectedConsultant?.id ?? 0;
    // [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19] 进入加载：「今日用药」红点暂时不显示，防止首屏闪烁
    setReminderLoadingMap((prev) => ({ ...prev, [cid]: true }));
    try {
      const url = cid > 0
        ? `/api/medication-reminder/today?consultant_id=${cid}`
        : '/api/medication-reminder/today';
      const res: any = await api.get(url);
      const list = Array.isArray(res) ? res : (res?.data ?? []);
      const hasUnchecked = Array.isArray(list) && list.some((it: any) => !it.checked);
      const isEmpty = !Array.isArray(list) || list.length === 0;
      setReminderRedDotMap((prev) => ({ ...prev, [cid]: !!hasUnchecked }));
      setReminderEmptyMap((prev) => ({ ...prev, [cid]: !!isEmpty }));
    } catch {
      // 接口失败按"无红点"处理（保守）
      setReminderRedDotMap((prev) => ({ ...prev, [cid]: false }));
    } finally {
      setReminderLoadingMap((prev) => ({ ...prev, [cid]: false }));
    }
  }, [selectedConsultant]);

  useEffect(() => {
    refreshReminderRedDot();
  }, [refreshReminderRedDot, messages.length]);

  // [M1] handleUndoSwitch 已移除 — 蓝色横条撤销功能不再需要

  // [PRD-420 F6] 进入页面默认咨询对象为「本人」（不读取上次选择，不与菜单模式联动）
  useEffect(() => {
    setSelectedConsultant(null);
    return () => {
      if (centerToastTimerRef.current) {
        clearTimeout(centerToastTimerRef.current);
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

  // [PRD-AI-HOME-OPTIM-V4 F-刷新-03] 关键修复 R3：废除 6 小时切片机制
  //
  // 旧版逻辑（BUG-461）：进入页面 / 切回 Tab / focus / pageshow 时调用 /api/chat-sessions/active-check，
  //                     若距上次活动 ≥ 6 小时则切片到新会话。
  // v4 已改为统一的 60 分钟刷新机制（loadLastSession + idleArchiveCheck），
  // 并且时间口径统一使用 updated_at（不再混用 lastDoneTimeRef / Ref / inactive_hours），
  // 因此本处的 6 小时切片机制已废除，避免与新机制相互干扰。
  //
  // 后端 /api/chat-sessions/active-check 接口保留以备老客户端调用，但 v4 H5 端不再使用。

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
    router.push('/health-profile?target=self&from=ai-chat');
  }, [router]);

  // [PRD-467 FR-05] 进入页面拉取一次用户字号设置（与会话页打通）
  // 未登录 / 接口异常 → 静默失败，使用默认 standard(14px)
  useEffect(() => {
    if (!isLoggedIn) return;
    api.get('/api/user/font-setting')
      .then((res: any) => {
        const data = res.data || res;
        const level = data.font_size_level;
        if (level && FONT_SIZE_MAP[level as FontSizeLevel] !== undefined) {
          setFontSizeLevel(level as FontSizeLevel);
        }
      })
      .catch(() => {
        // 静默失败，使用默认 standard(14px)
      });
  }, [isLoggedIn]);

  // [PRD-467 FR-02] 点击⋯菜单中的「扫一扫」：复用 /scan 已有扫码页
  const handleScan = useCallback(() => {
    setMoreMenuOpen(false);
    router.push('/scan');
  }, [router]);

  // [PRD-467 FR-02 / FR-06] 点击⋯菜单中的「字体大小」
  //  - 未登录：Toast「请先登录」+ 跳登录页
  //  - 已登录：关闭⋯菜单 → 在⋯按钮正下方弹出字号 popover
  //  - popover 打开时与⋯菜单互斥
  const handleFontSize = useCallback(() => {
    setMoreMenuOpen(false);
    if (!isLoggedIn) {
      showToast('请先登录', 'warning');
      router.push('/login');
      return;
    }
    setFontPopoverOpen(true);
  }, [isLoggedIn, router]);

  // [PRD-467 FR-03 / FR-05] 字号档位切换：立即生效 + 300ms debounce 持久化 + Toast
  // 失败时回滚到上一档字号 + Toast「保存失败，请重试」
  const handleFontChange = useCallback((level: FontSizeLevel) => {
    const prev = fontSizeLevel;
    setFontSizeLevel(level);
    setFontPopoverOpen(false);
    showToast(FONT_TOAST_MAP[level]);
    if (!isLoggedIn) return;
    if (fontSaveTimerRef.current) clearTimeout(fontSaveTimerRef.current);
    fontSaveTimerRef.current = setTimeout(() => {
      api.put('/api/user/font-setting', { font_size_level: level }).catch(() => {
        setFontSizeLevel(prev);
        showToast('保存失败，请重试', 'fail');
      });
    }, 300);
  }, [fontSizeLevel, isLoggedIn]);

  // [PRD-467 状态机 6] popover 外点击自动关闭
  useEffect(() => {
    if (!fontPopoverOpen) return;
    const handleClickOutside = (e: MouseEvent | TouchEvent) => {
      const target = e.target as Node;
      if (fontPopoverRef.current && !fontPopoverRef.current.contains(target)) {
        // 排除⋯按钮自身：⋯按钮的 onClick 会单独处理互斥
        const moreBtn = document.querySelector('[data-testid="ai-home-more-btn"]');
        if (moreBtn && moreBtn.contains(target)) return;
        setFontPopoverOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside as any);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside as any);
    };
  }, [fontPopoverOpen]);

  // [PRD-MODE-CAPSULE-V1 2026-05-31] 模式切换下拉胶囊：面板外点击自动收起
  useEffect(() => {
    if (!modeDropdownOpen) return;
    const handleClickOutside = (e: MouseEvent | TouchEvent) => {
      const target = e.target as Node;
      if (modeDropdownRef.current && !modeDropdownRef.current.contains(target)) {
        setModeDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside as any);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside as any);
    };
  }, [modeDropdownOpen]);

  // [PRD-MODE-CAPSULE-V1 2026-05-31] 切换到关怀模式（沿用现有逻辑：保存偏好→提示→跳转）
  const handleSwitchToCareMode = useCallback(async () => {
    if (modeSwitching) return;
    setModeSwitching(true);
    setModeDropdownOpen(false);
    try {
      const { saveModePreference } = await import('@/lib/mode-preference');
      await saveModePreference('care');
    } catch (e) {
      // 静默：偏好保存失败不阻塞跳转
      // eslint-disable-next-line no-console
      console.warn('[mode-capsule] 保存偏好失败', e);
    }
    try {
      showToast('已切换到关怀模式 ✓', { duration: 2000 } as any);
    } catch {
      try { (showToast as any)('已切换到关怀模式 ✓'); } catch { /* ignore */ }
    }
    router.push('/care-ai-home');
  }, [modeSwitching, router]);

  // [PRD-467 状态机 7] 组件卸载时清理 debounce 定时器
  useEffect(() => {
    return () => {
      if (fontSaveTimerRef.current) clearTimeout(fontSaveTimerRef.current);
    };
  }, []);

  // [PRD-467 FR-04] 字号仅作用于消息流气泡正文字号
  const chatFontSize = FONT_SIZE_MAP[fontSizeLevel];

  // [BUG_FIX_AI_HOME_3BUGS_20260517 · Bug B/C]
  // 进入历史会话时必须从 session 详情中回填 selectedConsultant，
  // 否则胶囊会粘着上次 APP 最后选的那个人（Bug B 现场），
  // 同时新发的消息会按"上次选的人"档案给建议（Bug C 现场）。
  // 权威字段：chat_session.family_member_id（后端 GET /api/chat/sessions/{id}
  // 已返回该字段及 family_member 简要档案）。
  const handleSelectSession = useCallback(async (sid: string) => {
    setMessages([]);
    currentSidRef.current = sid;
    setSessionId(sid);
    // [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 历史抽屉中点击进入的会话默认视为 archived；
    // 真实状态以详情接口返回的 status 字段为准（下方回填）。
    sidStatusRef.current = 'archived';
    setSidebarOpen(false);

    // 并行：拉详情回填咨询人 + 拉历史消息
    void (async () => {
      try {
        const detailRes: any = await api.get(`/api/chat/sessions/${sid}`);
        const detail = detailRes?.data ?? detailRes;
        const fmBrief = detail?.family_member;
        const fmId: number | null | undefined = detail?.family_member_id;
        // 回填会话状态：active 或 archived
        try {
          const st = (detail?.status || '').toLowerCase();
          if (st === 'active' || st === 'archived') {
            sidStatusRef.current = st as 'active' | 'archived';
          }
        } catch {
          /* ignore */
        }

        // 三态：
        //   - family_member 是 is_self 的 FamilyMember（后端 _ensure_self_family_member 写入）→ 视为本人态，胶囊回到「本人」
        //   - family_member 是其他成员 → 强制覆盖 selectedConsultant
        //   - family_member 缺失 / null → 视为本人态
        if (!fmBrief || !fmId) {
          setSelectedConsultant(null);
          return;
        }
        const isSelf = !!(fmBrief.is_self || fmBrief.relationship === '本人');
        if (isSelf) {
          setSelectedConsultant(null);
        } else {
          // 强制覆盖：会话维度的唯一权威源
          setSelectedConsultant({
            id: fmBrief.id,
            nickname: fmBrief.nickname || '家庭成员',
            relationship_type: fmBrief.relationship,
            relation_type_name: fmBrief.relationship,
            avatar: fmBrief.avatar,
            is_self: false,
          });
        }
      } catch {
        // 详情拉取失败不阻塞，保持当前胶囊状态（保守）
      }
    })();

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

  // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 宫格按"是否推荐"过滤，胶囊条按"是否胶囊"过滤
  // - 列数固定 4，行数不限（向下铺）
  // - 排序 sort_weight ASC, id ASC
  // - 两个开关均关闭的按钮在 C 端完全不显示（等同旧 is_enabled=false）
  // - 兜底：仅当 is_recommended/is_capsule 两个字段都是 undefined（老接口未升级）时，
  //   退化为按 is_enabled 过滤，避免升级窗口期宫格突然空白
  const _hasNewSwitchFields = funcButtons.some(
    (b) => typeof b.is_recommended === 'boolean' || typeof b.is_capsule === 'boolean',
  );
  const gridCols = 4;

  // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 宫格按 grid_sort 升序，胶囊按 capsule_sort 升序
  // 字段缺失时兜底到老 sort_weight，保证升级窗口期不乱序。
  const fnGridItems = funcButtons
    .slice()
    .filter((b) => {
      if (_hasNewSwitchFields) return !!b.is_recommended;
      return b.is_enabled !== false;
    })
    .sort((a, b) => {
      const av = (a.grid_sort ?? a.sort_weight ?? 0);
      const bv = (b.grid_sort ?? b.sort_weight ?? 0);
      return av - bv;
    });

  // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 胶囊条数据：按 is_capsule 过滤
  const capsuleButtons = funcButtons
    .slice()
    .filter((b) => {
      if (_hasNewSwitchFields) return !!b.is_capsule;
      return b.is_enabled !== false;
    })
    .sort((a, b) => {
      const av = (a.capsule_sort ?? a.sort_weight ?? 0);
      const bv = (b.capsule_sort ?? b.sort_weight ?? 0);
      return av - bv;
    });

  // [PRD-AIHOME-SKELETON-V1 2026-05-19] 移除「3 个内置兜底按钮」：
  //   旧逻辑：当 fnGridItems 为空时，回退到 aiHomeConfig.func_grid.items 或 FALLBACK_CONFIG.func_grid.items（含 g1/g2/g3 三个硬编码按钮）
  //   新逻辑：宫格仅由后端 /api/function-buttons 真实数据驱动；
  //          - 关键接口 OK + 数据为空 → 宫格区不渲染（不再回填硬编码按钮）
  //          - 关键接口失败 / 超时 → 由骨架屏内的「加载失败，点击重试」卡片承接，绝不出现老兜底
  //   因此 fallbackGridItems 强制为空数组，gridItems 不再向 FnCell 提供任何数据。
  const fallbackGridItems: FuncGridItemCfg[] = [];
  const gridItems = fnGridItems.length > 0 ? null : fallbackGridItems;
  // 标记：宫格曝光埋点的按钮 id 列表
  const gridExposureIds = fnGridItems.map((b) => b.id);

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

  // [PRD-AIHOME-OPTIM-V1 2026-05-17 R3] 汉堡图标右上角红点：
  //   未读系统消息数 > 0 OR 待使用订单数 > 0 → 显示；两者都为 0 才隐藏
  //   unreadCount 为 null（未登录/接口异常）时按 0 处理，避免误显示
  const hamburgerDotVisible = (
    (typeof unreadCount === 'number' && unreadCount > 0) ||
    pendingUseOrderCount > 0
  );

  // [PRD-AIHOME-OPTIM-V1 2026-05-17 R2] 汉堡图标尺寸：
  // 高度 = "小康"字号 17px，宽度按原图标 22:18≈1.222 等比缩放
  // 三条横线：粗细 = 高度 * 2/18，间距 = 高度 * 4/18（与原 18px 高时的 2px/4px 等比）
  const TITLE_FONT_SIZE = 17;
  const HAMBURGER_HEIGHT = TITLE_FONT_SIZE;
  const HAMBURGER_WIDTH = Math.round((HAMBURGER_HEIGHT * 22) / 18); // ≈ 21
  const BAR_HEIGHT = Math.max(1, Math.round((HAMBURGER_HEIGHT * 2) / 18)); // ≈ 2
  const GAP = Math.max(1, Math.round((HAMBURGER_HEIGHT * 4) / 18)); // ≈ 4

  // [PRD-AIHOME-OPTIM-V1 2026-05-17 R1] 计算铃铛在 banner 区域垂直正中的初始 top
  // 以 banner 区域（健康贴士轮播卡 ≈130px 高）的 DOM 位置为锚，初始 top = banner.top + banner.height/2 - 铃铛高度/2
  // banner 不存在（接口为空）时回退到欢迎区下方默认位置
  useEffect(() => {
    if (typeof window === 'undefined') return;
    // 用 rAF 等待 banner DOM 完成布局
    let cancelled = false;
    let raf = 0;
    const computeOnce = () => {
      if (cancelled) return;
      const el = bannerAnchorRef.current;
      if (el) {
        const rect = el.getBoundingClientRect();
        if (rect && rect.height > 0) {
          const bellHeight = 36;
          const next = Math.max(56, Math.round(rect.top + rect.height / 2 - bellHeight / 2));
          setBellInitialTop(next);
          return;
        }
      }
      // 容错：banner 未渲染时使用 topbar(48) + 欢迎区(72) 之下的位置兜底
      setBellInitialTop(120);
    };
    raf = window.requestAnimationFrame(() => {
      window.requestAnimationFrame(computeOnce);
    });
    return () => {
      cancelled = true;
      if (raf) window.cancelAnimationFrame(raf);
    };
  }, [banners.length]);

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
      className="ai-home-root"
      data-testid="ai-home-root"
      style={{
        position: 'relative',
        maxWidth: 750,
        margin: '0 auto',
        height: '100vh',
        overflow: 'hidden',
      }}
    >
      {/* [PRD-AIHOME-SKELETON-V1 2026-05-19] 首屏骨架屏（loading/failed 时展示，
          淡出阶段 ready 之前仍然渲染，与真实内容 200ms 交叠淡入淡出） */}
      {firstScreenStatus !== 'ready' && (
        <AiHomeSkeleton
          className={skeletonFading ? 'fade-out' : ''}
          showError={firstScreenStatus === 'failed'}
          onRetry={handleRetryFirstScreen}
        />
      )}

    <div
      className={`flex flex-col h-screen ai-home-content ${
        skeletonFading || firstScreenStatus === 'ready' ? 'fade-in' : ''
      }`}
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
            background: 'linear-gradient(180deg, #F0F9FF 0%, #DBEAFE 100%)',
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
            {/* [PRD-AIHOME-OPTIM-V1 2026-05-17 R2/R3] 左：汉堡菜单按钮
                - 图标改为 SVG 三横线：第1、2条全长，第3条 50% 长度左对齐
                - 整体高度 = "小康"字号 17px，宽度按 22:18 等比缩放 ≈ 21px
                - 三条横线等粗，间距与原版等比缩放
                - 与"小康"文字顶端对齐（按钮 hit-zone 仍保持 32x32 以维持点击热区）
                - 右上角外侧添加 8px 红色实心圆（未读系统消息数>0 OR 待使用订单数>0 时显示） */}
            {topbarShowSidebar ? (
              <button
                className="flex items-center justify-center"
                style={{
                  position: 'absolute',
                  left: 8,
                  // [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19 §3.2 方案 A]
                  // 汉堡水平中线 ≡ "小康"文字视觉中线：按钮 32x32 在 48px 工作区内垂直居中
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: 32,
                  height: 32,
                  color: THEME.textPrimary,
                  background: 'transparent',
                  border: 'none',
                  padding: 0,
                  margin: 0,
                  lineHeight: 1,
                  cursor: 'pointer',
                  // SVG 在按钮内部居中 → 与"小康"文字视觉中线对齐
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                onClick={() => setSidebarOpen(true)}
                aria-label="历史会话"
                data-testid="ai-home-hamburger-btn"
              >
                <span
                  style={{
                    position: 'relative',
                    display: 'inline-block',
                    width: HAMBURGER_WIDTH,
                    height: HAMBURGER_HEIGHT,
                  }}
                >
                  <svg
                    width={HAMBURGER_WIDTH}
                    height={HAMBURGER_HEIGHT}
                    viewBox={`0 0 ${HAMBURGER_WIDTH} ${HAMBURGER_HEIGHT}`}
                    aria-hidden="true"
                    data-testid="ai-home-hamburger-icon"
                  >
                    {/* [BUGFIX-AI-HOME-5ITEMS-V1 2026-05-26 Bug#1] 三横线全部左对齐 (x=0)
                        - 第 1、2 条：等长，约 76% 宽度（≈16px）
                        - 第 3 条：更短，约 52% 宽度（≈11px）
                        视觉效果：左侧对齐，向右伸出不同长度，呈"阶梯递减" */}
                    {/* 第 1 条：76% 长度，左对齐 */}
                    <rect
                      x={0}
                      y={0}
                      width={Math.round(HAMBURGER_WIDTH * 0.76)}
                      height={BAR_HEIGHT}
                      rx={BAR_HEIGHT / 2}
                      fill="currentColor"
                    />
                    {/* 第 2 条：76% 长度，左对齐 */}
                    <rect
                      x={0}
                      y={BAR_HEIGHT + GAP}
                      width={Math.round(HAMBURGER_WIDTH * 0.76)}
                      height={BAR_HEIGHT}
                      rx={BAR_HEIGHT / 2}
                      fill="currentColor"
                    />
                    {/* 第 3 条：52% 长度，左对齐（比 1/2 更短） */}
                    <rect
                      x={0}
                      y={(BAR_HEIGHT + GAP) * 2}
                      width={Math.round(HAMBURGER_WIDTH * 0.52)}
                      height={BAR_HEIGHT}
                      rx={BAR_HEIGHT / 2}
                      fill="currentColor"
                    />
                  </svg>
                  {hamburgerDotVisible && (
                    <span
                      data-testid="ai-home-hamburger-reddot"
                      aria-label="有新消息或待使用订单"
                      style={{
                        position: 'absolute',
                        // 红点左下角紧贴图标右上角顶点 → 左下角 (left:WIDTH, top:-8)
                        left: HAMBURGER_WIDTH,
                        top: -8,
                        width: 8,
                        height: 8,
                        borderRadius: 9999,
                        background: '#FF3B30',
                        border: 'none',
                        boxShadow: 'none',
                        pointerEvents: 'none',
                      }}
                    />
                  )}
                </span>
              </button>
            ) : null}

            {/* [BUGFIX-AI-HOME-5ITEMS-V1 2026-05-26 Bug#2] "小康"严格水平居中
                - 容器改为绝对定位，left:50%; transform:translateX(-50%)；
                - 与窗口（顶栏 max-width 750px 容器）水平中线对齐；
                - 不再贴着 ☰，三横线右边那块区域空出不补任何内容；
                - ☰ 仍保持左上角（left:8）、+ 仍保持右上角（right:8） */}
            <div
              style={{
                position: 'absolute',
                left: '50%',
                transform: 'translateX(-50%)',
                top: 0,
                bottom: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                minWidth: 0,
                /* 限制最大宽度，长签名时按原标题截断逻辑（>8 字符已加…），不会顶到左右按钮 */
                maxWidth: 'calc(100% - 120px)',
              }}
            >
              <span
                className="relative inline-block"
                style={{
                  fontSize: 18,
                  fontWeight: 600,
                  color: '#0C4A6E',
                  // [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19 §3.2] lineHeight:1 关闭额外行高带来的不可见偏移，
                  // 保证"小康"文字视觉中线与汉堡水平中线对齐误差 ≤ 1px
                  lineHeight: 1,
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

            {/*
              [PRD-AI-HOME-V1 2026-05-19] 邀请图标：位于「⋯」更多菜单按钮左侧。
                - 位置：right = 8(⋯ 按钮 right) + 32(⋯ 按钮宽) + 4(间距) = 44
                - 视觉：🎁 礼物图标（纯图标，不带文字/红点），尺寸 32x32 与⋯按钮一致
                - 行为：router.push('/invite')；/invite 路由项目已存在
                - 显隐：始终展示（产品要求新增的全局入口）
            */}
            <button
              type="button"
              className="flex items-center justify-center"
              style={{
                position: 'absolute',
                right: 44,
                top: '50%',
                transform: 'translateY(-50%)',
                width: 32,
                height: 32,
                color: THEME.textPrimary,
                background: 'transparent',
                border: 'none',
                padding: 0,
                margin: 0,
                lineHeight: 1,
                cursor: 'pointer',
              }}
              onClick={() => router.push('/invite')}
              aria-label="邀请好友"
              data-testid="ai-home-invite-btn"
            >
              <span style={{ fontSize: 20, lineHeight: 1 }} aria-hidden="true">
                🎁
              </span>
            </button>

            {/* [PRD-MODE-CAPSULE-V1 2026-05-31] AI 首页右上角「模式切换」下拉胶囊（方案 A）
                - 用一个下拉胶囊替代原「标准模式徽章 + 关怀模式按钮」两个独立控件
                - 收起态：胶囊内仅显示「当前模式文字 + 下拉箭头 ▾」，整体可点
                - 展开态：箭头翻转朝上 ▴，下方弹出面板，含「标准模式 / 关怀模式」两行
                - 当前模式（标准）高亮并打勾 ✓；点当前模式或面板外仅收起、不切换
                - 点关怀模式 → 沿用现有切换逻辑：保存偏好 → Toast → 跳 /care-ai-home
                - 位置：邀请按钮(right:44, w:32)的左侧，整体 absolute 定位 right:80
            */}
            <div
              ref={modeDropdownRef}
              style={{
                position: 'absolute',
                right: 80,
                top: '50%',
                transform: 'translateY(-50%)',
              }}
              data-testid="ai-home-mode-switcher"
            >
              <button
                type="button"
                onClick={() => setModeDropdownOpen((v) => !v)}
                disabled={modeSwitching}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  background: '#E3F2FD',
                  color: '#1976D2',
                  border: 'none',
                  padding: '5px 10px',
                  borderRadius: 14,
                  fontSize: 13,
                  fontWeight: 600,
                  lineHeight: 1,
                  whiteSpace: 'nowrap',
                  cursor: modeSwitching ? 'default' : 'pointer',
                  minHeight: 28,
                }}
                aria-haspopup="listbox"
                aria-expanded={modeDropdownOpen}
                aria-label="模式切换"
                data-testid="ai-home-mode-capsule"
              >
                <span data-testid="ai-home-mode-capsule-label">标准模式</span>
                <span
                  aria-hidden="true"
                  style={{
                    display: 'inline-block',
                    fontSize: 10,
                    lineHeight: 1,
                    transform: modeDropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.15s ease',
                  }}
                  data-testid="ai-home-mode-capsule-arrow"
                >
                  ▾
                </span>
              </button>

              {modeDropdownOpen ? (
                <div
                  role="listbox"
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 6px)',
                    right: 0,
                    minWidth: 120,
                    background: '#FFFFFF',
                    borderRadius: 10,
                    boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                    border: '1px solid #E5E7EB',
                    overflow: 'hidden',
                    zIndex: 50,
                  }}
                  data-testid="ai-home-mode-dropdown-panel"
                >
                  {/* 标准模式（当前模式：高亮 + 打勾，点击仅收起不切换） */}
                  <div
                    role="option"
                    aria-selected={true}
                    onClick={() => setModeDropdownOpen(false)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                      padding: '10px 14px',
                      fontSize: 14,
                      fontWeight: 600,
                      color: '#1976D2',
                      background: '#E3F2FD',
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                    data-testid="ai-home-mode-option-standard"
                  >
                    <span>标准模式</span>
                    <span aria-hidden="true">✓</span>
                  </div>
                  {/* 关怀模式（点击触发切换流程） */}
                  <div
                    role="option"
                    aria-selected={false}
                    onClick={handleSwitchToCareMode}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                      padding: '10px 14px',
                      fontSize: 14,
                      fontWeight: 500,
                      color: '#374151',
                      background: '#FFFFFF',
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                    data-testid="ai-home-mode-option-care"
                  >
                    <span>关怀模式</span>
                    <span aria-hidden="true" style={{ width: 14 }} />
                  </div>
                </div>
              ) : null}
            </div>

            {/* [BUGFIX-AI-HOME-5ITEMS-V1 2026-05-26 Bug#3a] "⋯" 改为 "+加圆圈"（微信样式）
                - 圆形描边、无填充；内部为"+"号；
                - 颜色 / 点击热区 32x32 / onClick 处理逻辑保持不变，菜单功能完整保留 */}
            {topbarShowMoreMenu ? (
              <button
                className="flex items-center justify-center"
                style={{
                  position: 'absolute',
                  right: 8,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: 32,
                  height: 32,
                  color: THEME.textPrimary,
                  background: 'transparent',
                  border: 'none',
                  padding: 0,
                  margin: 0,
                  lineHeight: 1,
                  cursor: 'pointer',
                }}
                onClick={() => {
                  // [PRD-467 状态机 5] popover 打开时再点 +：popover 关闭并打开菜单（互斥）
                  if (fontPopoverOpen) setFontPopoverOpen(false);
                  setMoreMenuOpen(true);
                }}
                aria-label="更多菜单"
                data-testid="ai-home-more-btn"
              >
                <svg
                  width={22}
                  height={22}
                  viewBox="0 0 22 22"
                  aria-hidden="true"
                  data-testid="ai-home-more-icon-plus-circle"
                >
                  <circle
                    cx={11}
                    cy={11}
                    r={9.5}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.6}
                  />
                  <line
                    x1={11}
                    y1={6}
                    x2={11}
                    y2={16}
                    stroke="currentColor"
                    strokeWidth={1.6}
                    strokeLinecap="round"
                  />
                  <line
                    x1={6}
                    y1={11}
                    x2={16}
                    y2={11}
                    stroke="currentColor"
                    strokeWidth={1.6}
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            ) : null}

            {/* [PRD-467 FR-02/FR-03] 字号 popover：锚定在⋯按钮正下方，宽 160 / 行高 40 / 朝上小三角 */}
            {fontPopoverOpen && (
              <div
                ref={fontPopoverRef}
                data-testid="ai-home-font-popover"
                style={{
                  position: 'absolute',
                  top: 44,
                  right: 8,
                  width: 160,
                  background: THEME.background, // #F0F9FF
                  border: '1px solid #BAE6FD',
                  borderRadius: 8,
                  boxShadow: '0 4px 12px rgba(14,165,233,0.15)',
                  padding: '6px 0',
                  zIndex: 110,
                }}
              >
                {/* 朝上小三角：对齐⋯按钮中心 */}
                <span
                  style={{
                    position: 'absolute',
                    top: -5,
                    right: 14,
                    width: 8,
                    height: 8,
                    background: THEME.background,
                    borderTop: '1px solid #BAE6FD',
                    borderLeft: '1px solid #BAE6FD',
                    transform: 'rotate(45deg)',
                  }}
                />
                {(['standard', 'large', 'extra_large'] as FontSizeLevel[]).map((level) => {
                  const isActive = fontSizeLevel === level;
                  const size = FONT_SIZE_MAP[level];
                  return (
                    <div
                      key={level}
                      data-testid={`ai-home-font-option-${level}`}
                      onClick={() => handleFontChange(level)}
                      style={{
                        height: 40,
                        padding: '0 12px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                      }}
                      onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = '#E0F2FE'; }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                    >
                      <span style={{ fontSize: 14, color: THEME.textPrimary }}>{FONT_LABEL_MAP[level]}</span>
                      {isActive ? (
                        <span style={{ color: '#0EA5E9', fontSize: 14, fontWeight: 600 }}>✓</span>
                      ) : (
                        <span style={{ color: '#9CA3AF', fontSize: 12 }}>{size}px</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
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
                  {/* [PRD-449 R3 + R5 + R6] 欢迎区大头像（A 位）改用 AiAvatar 公共组件
                      统一处理「取后台 → 兜底 → 占位」三段逻辑：
                      - 后台返回 image_url（http(s) 或 / 开头相对路径）→ 加载完成后平滑切换显示
                      - 后台返回 emoji（如 🌿）→ 渲染 emoji 字符
                      - 接口失败 / 字段为空 / URL 404 / 加载失败 → 显示默认"宾尼小康"图（修复历史裂图 BUG） */}
                  <AiAvatar
                    src={
                      aiHomeConfig.welcome?.avatar?.type === 'image'
                        ? aiHomeConfig.welcome?.avatar?.image_url
                        : aiHomeConfig.welcome?.avatar?.emoji
                    }
                    size={56}
                    shape="circle"
                    alt="AI 头像"
                    testId="ai-home-welcome-avatar"
                  />
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
                <div
                  ref={bannerAnchorRef}
                  className="rounded-2xl overflow-hidden mb-4 shadow-lg"
                  style={{ background: 'var(--gradient-primary)' }}
                  data-prd447="health-tips-card"
                  data-testid="ai-home-banner-anchor"
                >
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
                            backgroundColor: '#0EA5E9',
                          }}
                          onClick={() => banner.link_url && router.push(banner.link_url)}
                        />
                      </Swiper.Item>
                    ))}
                  </Swiper>
                </div>
              )}
            </SectionErrorBoundary>

            {/* [AICHAT-OPTIM-FIX-V1 F-04/F-06 2026-05-14] 功能宫格：数据源统一到 chat_function_buttons */}
            <SectionErrorBoundary name="func_grid">
              {/* [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 新版功能宫格
                  - 4 列固定、行数不限（按需向下铺）、按 sort_weight ASC 排序
                  - 单元格：56×56 图标外层圆角背景框（取 AI 专属 5 色循环配色池），下方 13px 名称
                  - 图标三级兜底：icon_url（图片）> icon（emoji）> button_type 自动匹配
                  - 点击：scale(0.96) 按压态 + 复用 handleFunctionButtonClick */}
              {funcGridVisible && fnGridItems.length > 0 && (
                <div
                  className="grid mb-4"
                  data-testid="ai-home-func-grid"
                  data-grid-cols={gridCols}
                  data-grid-source="chat_function_buttons_v2"
                  style={{
                    gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                    columnGap: 12,
                    rowGap: 16,
                  }}
                  ref={(el) => {
                    if (el && !(el as any).__exposed && gridExposureIds.length > 0) {
                      (el as any).__exposed = true;
                      try { aiHomeFnTrack.menuExposure(gridExposureIds); } catch {}
                    }
                  }}
                >
                  {fnGridItems.map((btn, idx) => {
                    const color = getAiGridColor(idx);
                    const ic = resolveAiGridIcon(btn);
                    return (
                      <div
                        key={btn.id}
                        data-testid={`bh-fn-cell-${btn.id}`}
                        onClick={() => {
                          try { aiHomeFnTrack.menuClick(btn.id, btn.name, btn.button_type); } catch {}
                          handleFunctionButtonClick(btn);
                        }}
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'flex-start',
                          cursor: 'pointer',
                          transition: 'transform 200ms ease',
                          padding: 0,
                          userSelect: 'none',
                        }}
                        onTouchStart={(e) => {
                          (e.currentTarget as HTMLDivElement).style.transform = 'scale(0.96)';
                        }}
                        onTouchEnd={(e) => {
                          (e.currentTarget as HTMLDivElement).style.transform = 'scale(1)';
                        }}
                        onTouchCancel={(e) => {
                          (e.currentTarget as HTMLDivElement).style.transform = 'scale(1)';
                        }}
                        onMouseDown={(e) => {
                          (e.currentTarget as HTMLDivElement).style.transform = 'scale(0.96)';
                        }}
                        onMouseUp={(e) => {
                          (e.currentTarget as HTMLDivElement).style.transform = 'scale(1)';
                        }}
                        onMouseLeave={(e) => {
                          (e.currentTarget as HTMLDivElement).style.transform = 'scale(1)';
                        }}
                      >
                        <div
                          style={{
                            width: 56,
                            height: 56,
                            borderRadius: 16,
                            background: color.bg,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            marginBottom: 8,
                          }}
                          aria-label={btn.name}
                        >
                          {ic.type === 'image' ? (
                            <img
                              src={ic.value}
                              alt={btn.name}
                              style={{ width: 28, height: 28, objectFit: 'contain' }}
                            />
                          ) : (
                            <span
                              style={{
                                fontSize: 24,
                                lineHeight: 1,
                                color: color.main,
                                display: 'inline-block',
                              }}
                            >
                              {ic.value}
                            </span>
                          )}
                        </div>
                        <span
                          style={{
                            fontSize: 13,
                            lineHeight: '18px',
                            color: '#1F2937',
                            textAlign: 'center',
                            width: '100%',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            paddingLeft: 2,
                            paddingRight: 2,
                          }}
                        >
                          {btn.name}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
              {/* 兜底：fnGridItems 为空时显示静态配置 / FALLBACK 3 项 */}
              {funcGridVisible && fnGridItems.length === 0 && gridItems && gridItems.length > 0 && (
                <div
                  className={`grid gap-3 mb-4`}
                  data-testid="ai-home-func-grid"
                  data-grid-source="fallback"
                  style={{ gridTemplateColumns: `repeat(${gridCols}, minmax(0, 1fr))` }}
                >
                  {gridItems.map(it => (
                    <FnCell
                      key={it.id}
                      icon={it.icon || '📌'}
                      main={it.main_text}
                      sub={it.sub_text}
                      badge={it.badge || undefined}
                      onClick={() => {
                        // [PRD-AI-HOME-V1 2026-05-19] target_path 运行时兜底：
                        //   (tabs) 路由组已下线，所有指向旧 (tabs)/services 路径的 DB 配置
                        //   都需自动重定向到独立 /services 路由。
                        //   - `/(tabs)/services` / `/tabs/services` → `/services`
                        //   - 空值或非法值 → 跳 `/services`（服务为宫格的默认兜底语义）
                        let p = it.target_path;
                        if (!p) {
                          if (typeof console !== 'undefined') console.warn('[ai-home grid] target_path empty, fallback to /services', it);
                          router.push('/services');
                          return;
                        }
                        const legacy = p.replace(/^\/?\(tabs\)/, '').replace(/^\/?tabs\//, '/');
                        if (legacy !== p) {
                          if (typeof console !== 'undefined') console.warn('[ai-home grid] legacy (tabs) path rewritten:', p, '->', legacy);
                          p = legacy;
                        }
                        if (p.startsWith('http')) window.location.href = p;
                        else if (p.startsWith('/')) router.push(p);
                        else {
                          if (typeof console !== 'undefined') console.warn('[ai-home grid] invalid target_path, fallback to /services:', p);
                          router.push('/services');
                        }
                      }}
                      testId={`bh-fn-cell-${it.id}`}
                    />
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

            {/* [PRD-BELL-UNIFIED-V1 2026-05-19] AI 首页"今日待办"胶囊
                - 位置：LOGO（欢迎区）下方、"还没有对话记录"提示文案上方
                - 始终显示，无论待办数是否为 0
                - 点击 = 打开铃铛抽屉 */}
            <SectionErrorBoundary name="today_todo_capsules">
              {messages.length === 0 && (
                <TodayTodoCapsules onOpenDrawer={() => setReminderOpen(true)} />
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

              // [PRD-AI-HOME-OPTIM-V4 M2 · F-切人-02] 系统切换通知：居中、灰色细文字、两侧短破折号、永久留痕
              if ((msg as any).kind === 'system_switch_notice') {
                return (
                  <div
                    key={msg.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'center',
                      margin: '16px 0',
                    }}
                    data-testid="system-switch-notice"
                  >
                    <span
                      style={{
                        fontSize: 12,
                        color: '#9CA3AF',
                        lineHeight: 1.4,
                        textAlign: 'center',
                        padding: '0 16px',
                      }}
                    >
                      {msg.content}
                    </span>
                  </div>
                );
              }
              // [PRD-433 F-06] 操作按钮行：所有非流式 AI 消息都显示（不仅 lastAiMsg）
              const showAiActions = !isUser && !msg.isStreaming;
              const senderName = '小康';
              const disclaimerText = 'AI 生成内容仅供参考，不作为诊断依据';
              const hasReferences = !isUser && Array.isArray(msg.references) && msg.references.length > 0;

              // [AICHAT-OPTIM-FIX-V1 F-06] 检测特殊"卡片消息"，渲染 ChatCard 组件
              let chatCardData: { kind: string; cardType: ChatCardType; button: any } | null = null;
              if (!isUser && typeof msg.content === 'string' && msg.content.startsWith('{') && msg.content.includes('"kind":"ai-chat-card"')) {
                try {
                  const parsed = JSON.parse(msg.content);
                  if (parsed && parsed.kind === 'ai-chat-card' && parsed.button) {
                    chatCardData = parsed;
                  }
                } catch {}
              }
              if (chatCardData && !isUser) {
                return (
                  <div key={msg.id} style={{ marginBottom: 24 }} data-testid="ai-home-ai-card-msg">
                    <div className="flex items-center" style={{ marginBottom: 6, paddingLeft: 16 }}>
                      <AiAvatar
                        src={aiHomeConfig.welcome?.avatar?.type === 'image' ? aiHomeConfig.welcome?.avatar?.image_url : aiHomeConfig.welcome?.avatar?.emoji}
                        size={28}
                        shape="circle"
                        alt="AI 头像"
                        testId="ai-home-msg-avatar"
                      />
                      <span style={{ marginLeft: 8, fontSize: 14, color: '#666' }}>{senderName}</span>
                    </div>
                    <div style={{ marginLeft: 16, marginRight: 16 }} data-testid="ai-home-chatcard-wrapper">
                      <ChatCard
                        cardType={chatCardData.cardType}
                        button={chatCardData.button}
                        onAction={(sub) => {
                          try { aiHomeFnTrack.cardButtonClick(chatCardData!.button.key, chatCardData!.cardType); } catch {}
                          // navigate 类型：跳 external_url
                          if (chatCardData!.cardType === 'navigate' && chatCardData!.button.externalUrl) {
                            const url = chatCardData!.button.externalUrl;
                            if (url.startsWith('http')) window.location.href = url;
                            else router.push(url);
                            return;
                          }
                          // quick_ask 类型：发预设话术
                          if (chatCardData!.cardType === 'quick_ask') {
                            const text = (chatCardData!.button.presetPrompt || chatCardData!.button.autoUserMessage || '').trim();
                            if (text) { lastMsgTimeRef.current = Date.now(); handleSend(text, 'preset'); }
                            return;
                          }
                          // [Bug-471 2026-05-15] upload 类型 4 按钮：相册 / 拍照 / 本机 / 微信
                          // 全部走"留在对话内"的同一套：选图 → 上传到服务器拿 URL → 对话区先冒图片
                          // 气泡 → 再触发 AI 回复识别 / 解读结果。
                          // 注意：photo_recognize_drug / drug_identify / medication_recognize / report_interpret
                          // 也走这里，不再跳 /drug 或 /checkup 独立页（修复 Bug-471 §3.1）。
                          if (chatCardData!.cardType === 'upload') {
                            const btnType = String(chatCardData!.button.buttonType || '');
                            const isFileType = btnType === 'file_upload';
                            const kindForPick: 'image' | 'file' = isFileType ? 'file' : 'image';
                            const presetPrompt = (chatCardData!.button as any).presetPrompt || null;
                            const autoUserMessage = chatCardData!.button.autoUserMessage || null;
                            const buttonName = chatCardData!.button.title || null;
                            const fallbackPrompt = resolveUploadFallbackPrompt(btnType, kindForPick);
                            const triggerPick = (src: 'album' | 'camera') => {
                              pickAndUploadThenSend({
                                source: src,
                                kind: kindForPick,
                                presetPrompt,
                                autoUserMessage,
                                buttonName,
                                fallbackPrompt,
                                // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
                                buttonType: btnType,
                                buttonId: (chatCardData!.button as any).id || null,
                                // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
                                aiFunctionType: (chatCardData!.button as any).aiFunctionType
                                  || (chatCardData!.button as any).ai_function_type
                                  || null,
                                capturePurpose: (chatCardData!.button as any).capturePurpose
                                  || (chatCardData!.button as any).capture_purpose
                                  || null,
                              });
                            };
                            switch (sub) {
                              case 'album':
                                triggerPick('album');
                                return;
                              case 'camera':
                                triggerPick('camera');
                                return;
                              case 'history':
                                router.push('/report-history');
                                return;
                              case 'local':
                                // 兼容存量「本机」按钮：本机文件 = 相册（含 PDF）
                                pickAndUploadThenSend({
                                  source: 'album',
                                  kind: 'file',
                                  presetPrompt,
                                  autoUserMessage,
                                  buttonName,
                                  fallbackPrompt: resolveUploadFallbackPrompt(btnType, 'file'),
                                  // [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517]
                                  buttonType: btnType,
                                  buttonId: (chatCardData!.button as any).id || null,
                                  // [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
                                  aiFunctionType: (chatCardData!.button as any).aiFunctionType
                                    || (chatCardData!.button as any).ai_function_type
                                    || null,
                                  capturePurpose: (chatCardData!.button as any).capturePurpose
                                    || (chatCardData!.button as any).capture_purpose
                                    || null,
                                });
                                return;
                              case 'wechat':
                                // H5 没有"微信选图"原生能力，给出友好提示后退化到相册
                                try { showToast('请先把图片保存到相册，再从相册中选择', 'warning'); } catch {}
                                triggerPick('album');
                                return;
                              default: {
                                // 未识别子动作：兜底走 autoUserMessage
                                const auto = (autoUserMessage || '').trim();
                                if (auto) { lastMsgTimeRef.current = Date.now(); handleSend(auto, 'preset'); }
                                return;
                              }
                            }
                          }
                          // sdk_call 等其它类型：发 autoUserMessage（如有）
                          const auto = (chatCardData!.button.autoUserMessage || '').trim();
                          if (auto) { lastMsgTimeRef.current = Date.now(); handleSend(auto, 'preset'); }
                        }}
                      />
                    </div>
                  </div>
                );
              }

              // [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 4.1] 用户上传的图片消息（来自 upload 类胶囊 / 卡片）
              // [Bug-471 2026-05-15] 支持 1~5 张图：当 msg.images 数组非空时渲染横向小图墙；
              // 兼容存量数据：msg.images 为空时回退到单图（msg.content）。
              if (isUser && msg.kind === 'image') {
                const imgs: string[] =
                  Array.isArray(msg.images) && msg.images.length > 0
                    ? msg.images
                    : (msg.content ? [msg.content] : []);
                if (imgs.length === 0) return null;
                const isMulti = imgs.length > 1;
                return (
                  <div key={msg.id} style={{ marginBottom: 24 }} data-testid="ai-home-user-image-message">
                    {showTime && (
                      <div className="text-center" style={{ padding: '8px 0' }} data-testid="ai-home-time-divider">
                        <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                          {formatWeChatTime(msg.time)}
                        </span>
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginRight: 16 }}>
                      <div
                        style={{
                          background: '#E6F0FF',
                          borderRadius: 14,
                          padding: 6,
                          maxWidth: 'min(75vw, 360px)',
                        }}
                        data-testid="ai-home-user-image-bubble"
                        data-image-count={imgs.length}
                      >
                        {isMulti ? (
                          <div
                            style={{
                              display: 'grid',
                              gridTemplateColumns: `repeat(${Math.min(imgs.length, 3)}, 1fr)`,
                              gap: 4,
                            }}
                          >
                            {imgs.map((u, idx) => (
                              <img
                                key={idx}
                                src={u}
                                alt={`用户上传 ${idx + 1}`}
                                style={{
                                  width: '100%',
                                  height: 86,
                                  borderRadius: 8,
                                  display: 'block',
                                  objectFit: 'cover',
                                  background: '#F3F4F6',
                                }}
                                data-testid="ai-home-user-image-thumb"
                              />
                            ))}
                          </div>
                        ) : (
                          <img
                            src={imgs[0]}
                            alt="用户上传"
                            style={{
                              maxWidth: '100%',
                              maxHeight: 240,
                              borderRadius: 10,
                              display: 'block',
                              objectFit: 'cover',
                            }}
                            data-testid="ai-home-user-image-thumb"
                          />
                        )}
                      </div>
                    </div>
                  </div>
                );
              }

              // [Bug-471 2026-05-15] 用户上传的非图片文件消息（如 PDF 文档）
              if (isUser && msg.kind === 'file' && Array.isArray(msg.files) && msg.files.length > 0) {
                return (
                  <div key={msg.id} style={{ marginBottom: 24 }} data-testid="ai-home-user-file-message">
                    {showTime && (
                      <div className="text-center" style={{ padding: '8px 0' }} data-testid="ai-home-time-divider">
                        <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                          {formatWeChatTime(msg.time)}
                        </span>
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginRight: 16, flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                      {msg.files.map((f, idx) => (
                        <div
                          key={idx}
                          style={{
                            background: '#E6F0FF',
                            color: '#1F2937',
                            borderRadius: 14,
                            padding: '10px 14px',
                            maxWidth: 'min(75vw, 360px)',
                            fontSize: 14,
                            wordBreak: 'break-all',
                          }}
                        >
                          📎 {f.name}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              }

              // [PRD-TCM-DRAWER-V12 2026-05-20] 通用问卷"对话内说明卡片"气泡（AI 侧）
              if (!isUser && msg.kind === 'questionnaire_pre_card' && msg.questionnairePreCard) {
                const pre = msg.questionnairePreCard;
                return (
                  <div
                    key={msg.id}
                    style={{ marginBottom: 24 }}
                    data-testid="ai-home-qn-pre-card-message"
                  >
                    {showTime && (
                      <div className="text-center" style={{ padding: '8px 0' }}>
                        <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                          {formatWeChatTime(msg.time)}
                        </span>
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'flex-start', marginLeft: 12, marginRight: 16, gap: 8 }}>
                      <AiAvatar size={32} />
                      <div style={{ flex: 1, maxWidth: 'min(80vw, 360px)' }}>
                        <QuestionnairePreCard
                          data={pre}
                          onStart={(d) => handlePreCardStart(d)}
                        />
                      </div>
                    </div>
                  </div>
                );
              }

              // [PRD-TAG-RECOMMEND-V1 2026-05-20] 推荐商品卡片气泡（AI 侧）
              if (msg.kind === 'questionnaire_recommend_card' && msg.questionnaireRecommend) {
                const rec = msg.questionnaireRecommend;
                return (
                  <div
                    key={msg.id}
                    style={{ marginBottom: 24 }}
                    data-testid="ai-home-qn-recommend-card-message"
                  >
                    {showTime && (
                      <div className="text-center" style={{ padding: '8px 0' }}>
                        <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                          {formatWeChatTime(msg.time)}
                        </span>
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'flex-start', marginLeft: 12, marginRight: 16, gap: 8 }}>
                      <AiAvatar size={32} />
                      <div style={{ flex: 1, maxWidth: 'min(92vw, 480px)' }}>
                        <QuestionnaireRecommendCard
                          goods={rec.goods}
                          clickMode={rec.clickMode}
                          onClickGoods={(g) => {
                            if (rec.clickMode === 'external') {
                              router.push(`/product/${g.id}`);
                            } else {
                              setRecommendDrawerGoods(g);
                              setRecommendDrawerOpen(true);
                            }
                          }}
                        />
                      </div>
                    </div>
                  </div>
                );
              }

              // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 问卷结果卡片气泡（AI 侧 · 修复 Bug-2/Bug-3）
              // - 强制 AI 侧（左对齐）：避免再次出现"用户气泡式总结"
              // - 优先使用 universalCard（含 main_type / 雷达 / 查看详情）
              if (!isUser && msg.kind === 'questionnaire_result_card' && msg.questionnaireResult) {
                const qr = msg.questionnaireResult;
                return (
                  <div
                    key={msg.id}
                    style={{ marginBottom: 24 }}
                    data-testid="ai-home-qn-result-card-message"
                  >
                    {showTime && (
                      <div className="text-center" style={{ padding: '8px 0' }}>
                        <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                          {formatWeChatTime(msg.time)}
                        </span>
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'flex-start', marginLeft: 12, marginRight: 16, gap: 8 }}>
                      <AiAvatar size={32} />
                      <div style={{ flex: 1, maxWidth: 'min(92vw, 480px)' }}>
                        {qr.universalCard ? (
                          <UniversalQuestionnaireResultCard
                            payload={qr.universalCard}
                            onClickDetail={(target) => {
                              // [BUG-TCM-RESULT-ID-FIX 2026-05-23] 优先使用 diagnosis_id
                              const code = qr.universalCard?.questionnaire_code;
                              const aid = qr.answerId;
                              const diagnosisId = target?.diagnosis_id || qr.universalCard?.diagnosis_id;
                              let route =
                                (target && target.route_h5) ||
                                (code === 'tcm_constitution' ? `/tcm/result/${diagnosisId || aid}` : null) ||
                                (code === 'health_self_check' ? `/health-self-check/result/${aid}` : null);
                              if (route) router.push(route);
                            }}
                          />
                        ) : (
                          <QuestionnaireResultCard
                            payload={qr.card}
                            aiStatusText={qr.aiStatusText}
                            onRetry={() => {
                              const btn = funcButtons.find(
                                (b) => Number(b.id) === Number(qr.buttonId),
                              );
                              if (btn) {
                                const df = (btn.questionnaire_display_form || 'DRAWER_SCROLL') as QnDisplayForm;
                                openQuestionnaireDrawer(btn, df).catch(() => {
                                  showToast('问卷加载失败', 'fail');
                                });
                              }
                            }}
                          />
                        )}
                      </div>
                    </div>
                  </div>
                );
              }

              // [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 追问 chips 行（AI 侧 · 修复 Bug-1）
              if (!isUser && msg.kind === 'followup_chips' && msg.followupChips) {
                const fc = msg.followupChips;
                return (
                  <div
                    key={msg.id}
                    style={{ marginBottom: 24 }}
                    data-testid="ai-home-followup-chips-message"
                  >
                    {showTime && (
                      <div className="text-center" style={{ padding: '8px 0' }}>
                        <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                          {formatWeChatTime(msg.time)}
                        </span>
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'flex-start', marginLeft: 12, marginRight: 16, gap: 8 }}>
                      <AiAvatar size={32} />
                      <FollowupChipsRow
                        chips={fc.chips || []}
                        disabled={!!fc.disabled}
                        onClickChip={async (chip) => {
                          // 立即置灰本行
                          setMessages((prev) =>
                            prev.map((x) =>
                              x.id === msg.id && x.followupChips
                                ? { ...x, followupChips: { ...x.followupChips, disabled: true } }
                                : x,
                            ),
                          );
                          try {
                            const r = await api.post<any>('/api/questionnaire/followup-chip', {
                              answer_id: fc.questionnaireResultId,
                              chip_code: chip.code,
                              chip_label: chip.label,
                            });
                            const aiText: string =
                              (r && r.ai_text) || `本次回答结合您的档案。${chip.label} 暂无更详细资料。`;
                            const aiMsg: ChatMessage = {
                              id: `qn-chip-reply-${Date.now()}`,
                              role: 'assistant',
                              content: aiText,
                              time: new Date().toISOString(),
                              kind: 'text',
                            };
                            setMessages((prev) => [...prev, aiMsg]);
                          } catch (e: any) {
                            console.warn('[ai-home] followup-chip failed', e);
                            showToast('请求失败，请稍后再试', 'fail');
                          }
                        }}
                      />
                    </div>
                  </div>
                );
              }

              // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查卡片气泡（用户侧）
              if (isUser && msg.kind === 'health_self_check_card' && msg.healthSelfCheck) {
                const payload = msg.healthSelfCheck;
                return (
                  <div key={msg.id} style={{ marginBottom: 24 }} data-testid="ai-home-hsc-card-message">
                    {showTime && (
                      <div className="text-center" style={{ padding: '8px 0' }} data-testid="ai-home-time-divider">
                        <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                          {formatWeChatTime(msg.time)}
                        </span>
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginRight: 16 }}>
                      <HealthSelfCheckCard
                        payload={{
                          archiveName: payload.archiveName,
                          archiveAge: payload.archiveAge,
                          archiveGender: payload.archiveGender,
                          bodyPart: payload.bodyPart,
                          symptoms: payload.symptoms,
                          duration: payload.duration,
                          symptomDescription: payload.symptomDescription,
                        }}
                        onReopen={() => {
                          const btn = funcButtons.find(
                            (b) => Number(b.id) === Number(payload.buttonId),
                          );
                          if (btn) {
                            setHscDrawerButton(btn);
                            setHscDrawerPrefill({
                              body_part: payload.bodyPart,
                              symptoms: payload.symptoms,
                              duration: payload.duration,
                              symptom_description: payload.symptomDescription,
                            });
                            setHscDrawerOpen(true);
                          }
                        }}
                      />
                    </div>
                  </div>
                );
              }

              // [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 4.2] QuickAskCard 卡片消息（用户编辑后才发送）
              if (isUser && msg.kind === 'quick_ask_card') {
                const qbtn = msg.quickAskButton!;
                const state = msg.quickAskState || 'pending';
                const cardDisabled = state !== 'pending';
                return (
                  <div key={msg.id} style={{ marginBottom: 24 }} data-testid="ai-home-quick-ask-card-message">
                    {showTime && (
                      <div className="text-center" style={{ padding: '8px 0' }} data-testid="ai-home-time-divider">
                        <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                          {formatWeChatTime(msg.time)}
                        </span>
                      </div>
                    )}
                    <div style={{ marginLeft: 16, marginRight: 16 }}>
                      <ChatCard
                        cardType="quick_ask"
                        disabled={cardDisabled}
                        button={{
                          key: String(qbtn.id),
                          buttonType: 'quick_ask',
                          title: qbtn.name,
                          iconEmoji: qbtn.icon || '⚡',
                          presetPrompt: msg.content,
                          autoUserMessage: qbtn.autoUserMessage,
                        }}
                        onAction={(sub, payload) => {
                          if (sub === 'send') {
                            handleQuickAskCardSend(msg.id, String(payload ?? ''));
                          } else if (sub === 'cancel') {
                            handleQuickAskCardCancel(msg.id);
                          }
                        }}
                      />
                      {state === 'sent' && (
                        <div style={{ marginTop: 4, textAlign: 'right', fontSize: 12, color: '#9CA3AF' }}>
                          已发送
                        </div>
                      )}
                      {state === 'cancelled' && (
                        <div style={{ marginTop: 4, textAlign: 'right', fontSize: 12, color: '#9CA3AF' }}>
                          已取消
                        </div>
                      )}
                    </div>
                  </div>
                );
              }

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
                          // [PRD-467 FR-04] 字号仅作用于消息流气泡正文
                          fontSize: chatFontSize,
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
                  {/* [PRD-433 F-03] AI 头像 + 名称行：保留在卡片外部上方，去掉「· 健康助手」
                      [PRD-449 R4 + R5] AI 消息小头像（B 位，28x28）改用 AiAvatar 公共组件，
                      复用「AI 对话模式首页配置 - 欢迎区 - 头像」同一字段（welcome.avatar），
                      不新增字段。三场景兜底（接口失败 / 字段为空 / 加载失败）统一显示默认"宾尼小康"图。 */}
                  <div className="flex items-center" style={{ marginBottom: 6, paddingLeft: 16 }}>
                    <AiAvatar
                      src={
                        aiHomeConfig.welcome?.avatar?.type === 'image'
                          ? aiHomeConfig.welcome?.avatar?.image_url
                          : aiHomeConfig.welcome?.avatar?.emoji
                      }
                      size={28}
                      shape="circle"
                      alt="AI 头像"
                      testId="ai-home-msg-avatar"
                    />
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
                    {/* [PRD-448 v1.2 §3.1] 咨询人胶囊：气泡内部第一行
                        渲染规则（v1.2 修复，取代 v1.1）：
                        进入此分支的页面已通过 isSelfMode 标志识别"本人"态，
                        与"已选定家庭成员"等价处理 → 本人态（selectedConsultant === null）
                        也进入胶囊渲染，传 consultantId=0 + memberName='本人' + isSelf=true。
                        不再用 `consultant === null` 判定为"未选择"，根因彻底修复。
                        未渲染条件：仅在极短的"页面初始化未确定咨询对象"时跳过（本项目中 ai-home
                        进入页面默认即设 isSelfMode，故不会出现"未选定"分支）。 */}
                    <div data-testid="ai-home-profile-card-wrapper" style={{ marginBottom: 8 }}>
                      <ProfileCard
                        consultantId={(msg.consultantTargetId ?? selectedConsultant?.id ?? 0) as number}
                        variant="capsule"
                        isSelf={!selectedConsultant && (msg.consultantTargetId === null || msg.consultantTargetId === undefined || msg.consultantTargetId === 0)}
                        memberName={
                          !selectedConsultant && (msg.consultantTargetId === null || msg.consultantTargetId === undefined || msg.consultantTargetId === 0)
                            ? '本人'
                            : (selectedConsultant?.nickname || undefined)
                        }
                        onGoComplete={(cid) => router.push(`/health-profile?target=${cid || 'self'}&from=ai-chat`)}
                        onGoMedicationManage={(cid, autoCreate) =>
                          router.push(`/ai-home/medication-plans${autoCreate ? '/new' : ''}?target=${cid || 'self'}`)
                        }
                      />
                    </div>
                    {/* 正文 */}
                    <div
                      className="ai-fullwidth-message"
                      style={{
                        // [PRD-467 FR-04] 字号仅作用于消息流气泡正文（AI 回答）
                        fontSize: chatFontSize,
                        lineHeight: 1.6,
                        color: THEME.textPrimary,
                        wordBreak: 'break-word',
                        overflowWrap: 'break-word',
                      }}
                    >
                      {/*
                       * [BUG_FIX_拍照识药三联_20260516] 聊天内嵌识药引擎结果分支：
                       *   - drug_identify_card → 复用 DrugIdentifyCard 组件（卡片样式 + 加入用药计划按钮预留）
                       *   - drug_identify_retake → 提示重新拍照气泡 + 「重新拍照」按钮（点击同 capsule 拍照入口）
                       *   - 其他 / null → 退化为普通 Markdown
                       */}
                      {/* [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F1~F3 2026-05-18]
                         * 「分阶段渐进淡入」：识药卡 4 卡按"基础信息 → 用法用量 → 安全提示 → 个性化风险"
                         * 顺序依次淡入。后端一次性 done meta 后，前端按时间窗渐进释放可见性，
                         * 配合卡片自身 260ms fadeIn 动画，达成 PRD §2.1 F1~F3 的"先轻后重"体验。
                         */}
                      {msg.drugMeta && msg.drugMeta.message_type === 'drug_identify_card' && Array.isArray(msg.drugMeta.medicines) && msg.drugMeta.medicines.length > 0 ? (
                        /* [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-1/2]
                         *   - 先渲染流式两段播报文本气泡（msg.content）
                         *   - 在气泡下方追加结构化识药卡片（4 模块 + 按钮固底）
                         *   - "已加入用药计划"状态写在 drugMeta.added_to_plan，跨刷新可恢复
                         */
                        <div data-testid="ai-home-drug-identify-card">
                          {msg.content && (
                            <div style={{ marginBottom: 8, fontSize: 15, color: '#333', lineHeight: 1.7 }}>
                              <span dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
                            </div>
                          )}
                          <DrugIdentifyCard
                            visibleSections={drugCardVisibleSectionsMap[msg.id] || { basic: true, usage: false, safety: false, risk: false }}
                            card={{
                              drug_name: msg.drugMeta.medicines[0]?.name || msg.drugMeta.medicines[0]?.brand || '已识别药品',
                              generic_name: msg.drugMeta.medicines[0]?.name || null,
                              brand_name: msg.drugMeta.medicines[0]?.brand || null,
                              spec: msg.drugMeta.medicines[0]?.spec || null,
                              dosage_form: (msg.drugMeta.medicines[0] as any)?.dosage_form || null,
                              manufacturer: msg.drugMeta.medicines[0]?.manufacturer || null,
                              approval_no: (msg.drugMeta.medicines[0] as any)?.approval_no || null,
                              category: msg.drugMeta.medicines[0]?.category || null,
                              indications: msg.drugMeta.medicines[0]?.indications || null,
                              usage: msg.drugMeta.medicines[0]?.usage || null,
                              usage_adult: (msg.drugMeta.medicines[0] as any)?.usage_adult || msg.drugMeta.medicines[0]?.usage || null,
                              usage_children: (msg.drugMeta.medicines[0] as any)?.usage_children || null,
                              timing: (msg.drugMeta.medicines[0] as any)?.timing || null,
                              contraindications: msg.drugMeta.medicines[0]?.contraindications || null,
                              adverse_reactions: (msg.drugMeta.medicines[0] as any)?.adverse_reactions || null,
                              interactions: (msg.drugMeta.medicines[0] as any)?.interactions || null,
                              special_population: (msg.drugMeta.medicines[0] as any)?.special_population || null,
                            }}
                            libraryMatched={Boolean(
                              msg.drugMeta.medicines[0]?.usage ||
                              msg.drugMeta.medicines[0]?.contraindications
                            )}
                            conflicts={[]}
                            personalizedRisk={msg.drugMeta.personalized_risk || null}
                            memberName={msg.drugMeta.member_name || null}
                            added={(() => {
                              // [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18 / F4]
                              // 优先使用 drugAddedMap（按当前咨询人维度），
                              // 兜底兼容 drugMeta.added_to_plan（旧版本字段）
                              const dn =
                                msg.drugMeta?.medicines?.[0]?.name ||
                                msg.drugMeta?.medicines?.[0]?.brand ||
                                '';
                              const cid = selectedConsultant?.id ?? 0;
                              const mapHit = drugAddedMap[`${cid}|${dn}`];
                              if (mapHit !== undefined) return mapHit;
                              return Boolean(msg.drugMeta.added_to_plan);
                            })()}
                            onAddPlan={async () => {
                              // [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18]
                              // 已加入态：弹二次确认
                              // 未加入态：直接打开抽屉
                              const dn =
                                msg.drugMeta?.medicines?.[0]?.name ||
                                msg.drugMeta?.medicines?.[0]?.brand ||
                                '';
                              const cid = selectedConsultant?.id ?? 0;
                              const isAdded =
                                drugAddedMap[`${cid}|${dn}`] ?? Boolean(msg.drugMeta?.added_to_plan);
                              if (isAdded) {
                                const ok = await Dialog.confirm({
                                  content: '该药已在用药计划中，是否再次加入 / 修改？',
                                });
                                if (!ok) return;
                              }
                              setActiveDrugMsgId(msg.id);
                              setActiveDrugCard({
                                drug_name: dn,
                                generic_name: msg.drugMeta?.medicines?.[0]?.name || null,
                                brand_name: msg.drugMeta?.medicines?.[0]?.brand || null,
                                spec: msg.drugMeta?.medicines?.[0]?.spec || null,
                                manufacturer: msg.drugMeta?.medicines?.[0]?.manufacturer || null,
                                disease_tags: (msg.drugMeta?.medicines?.[0] as any)?.disease_tags || null,
                              });
                              setAddMedDrawerOpen(true);
                            }}
                            onViewDetail={() => {
                              // [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19 §1.6.2]
                              // 「查看用药计划」 → 跳转「医药计划」三 Tab 列表页并强制定位到「服药中」Tab
                              router.push(`/ai-home/medication-plans?tab=in_progress`);
                            }}
                            onRetake={() => {
                              // [PRD-MED-PLAN-INTERACT-OPTIM-V1 §3.1.2] 重新拍照 → 弹出「拍照 / 相册选择」抽屉
                              setRetakeDrawerOpen(true);
                            }}
                            onViewAllPlans={() => {
                              // [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 抽屉内查看，不再跳页
                              setActiveDrugMsgId(msg.id);
                              setActiveDrugCard({
                                drug_name:
                                  msg.drugMeta?.medicines?.[0]?.name ||
                                  msg.drugMeta?.medicines?.[0]?.brand ||
                                  '',
                                generic_name: msg.drugMeta?.medicines?.[0]?.name || null,
                                brand_name: msg.drugMeta?.medicines?.[0]?.brand || null,
                                spec: msg.drugMeta?.medicines?.[0]?.spec || null,
                                manufacturer: msg.drugMeta?.medicines?.[0]?.manufacturer || null,
                                disease_tags: (msg.drugMeta?.medicines?.[0] as any)?.disease_tags || null,
                              });
                              setViewMedDrawerOpen(true);
                            }}
                            // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F9/F10/F11 2026-05-18]
                            // 用药提醒按钮：按"咨询人"维度判定红点 / 空状态 / 弹抽屉
                            onReminder={() => {
                              const cid = (msg.consultantTargetId ?? selectedConsultant?.id ?? 0) as number;
                              setReminderDrawerConsultantId(cid > 0 ? cid : null);
                              setReminderOpen(true);
                            }}
                            reminderRedDot={(() => {
                              const cid = (msg.consultantTargetId ?? selectedConsultant?.id ?? 0) as number;
                              return Boolean(reminderRedDotMap[cid]);
                            })()}
                            reminderDisabled={(() => {
                              const cid = (msg.consultantTargetId ?? selectedConsultant?.id ?? 0) as number;
                              return Boolean(reminderEmptyMap[cid]);
                            })()}
                            // [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19] 新 4 按钮所需 props
                            // 识药是否失败：drug_identify_card 已经渲染本身就表示识药成功；
                            // 历史 drug_identify_retake 那条消息会走另外的分支，不进入本卡片，
                            // 因此这里恒为 false（识药成功）
                            recognitionFailed={false}
                            hasTodayMedication={(() => {
                              const cid = (msg.consultantTargetId ?? selectedConsultant?.id ?? 0) as number;
                              return !reminderEmptyMap[cid];
                            })()}
                            loadingTodayMedication={(() => {
                              const cid = (msg.consultantTargetId ?? selectedConsultant?.id ?? 0) as number;
                              return Boolean(reminderLoadingMap[cid]);
                            })()}
                            // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F6] 整次识药重试 - 复用原图
                            onRetryAll={() => {
                              const urls = drugRetryImageMap[msg.id];
                              if (urls && urls.length > 0) {
                                // 1. 整条 AI 回答从聊天流中移除
                                setMessages((prev) => prev.filter((it) => it.id !== msg.id));
                                // 2. 用原图重走识药流程：直接调用 sendSSE
                                try {
                                  Toast.show({ content: 'AI 正在重新识别…', position: 'bottom' });
                                } catch {}
                                // 通过原图入口重新触发（与首次拍照后处理一致）
                                handleSend({
                                  text: '请识别此药品',
                                  sseExtras: { image_urls: urls },
                                } as any).catch(() => {});
                              } else {
                                try {
                                  Toast.show({ content: '图片信息已过期，请重新拍照识别', position: 'bottom' });
                                } catch {}
                                setRetakeDrawerOpen(true);
                              }
                            }}
                          />
                        </div>
                      ) : msg.drugMeta && msg.drugMeta.message_type === 'drug_identify_retake' ? (
                        <div data-testid="ai-home-drug-identify-retake" style={{ padding: '8px 12px', background: '#FFF7E6', borderRadius: 8, border: '1px solid #FFD591' }}>
                          <div style={{ marginBottom: 8 }}>
                            <span dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content || '识别结果不一致，请重新拍摄药盒清晰图。') }} />
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              // 触发拍照识药重拍：直接打开下方胶囊条/菜单的拍照入口
                              try {
                                Toast.show({ content: '请通过下方拍照按钮重新拍摄药盒', position: 'bottom' });
                              } catch {}
                            }}
                            style={{
                              minHeight: 36, padding: '4px 16px', background: '#FA8C16', color: '#fff',
                              border: 'none', borderRadius: 6, fontSize: 14, cursor: 'pointer',
                            }}
                          >
                            重新拍照
                          </button>
                        </div>
                      ) : (
                        /* [BUG_FIX_AI_HOME_ACTIONBAR_AND_ATTACHMENT_FILTER_20260517 · Bug-2]
                         * 普通文本 AI 回复渲染前：
                         *   1) sanitize 掉「内部协议提示语」整段
                         *   2) 把图片 URL（裸链接 + markdown 形态）从正文抽离到 imageUrls
                         *      下方紧贴文本渲染一行 80×80 小缩略图（横向滚动 / 全屏预览） */
                        (() => {
                          const sanitized = sanitizeAiContent(msg.content || '');
                          const { text: aiText, images: aiImageUrls } = extractImagesFromContent(sanitized);
                          return (
                            <>
                              {aiText && (
                                <span dangerouslySetInnerHTML={{ __html: renderMarkdown(aiText) }} />
                              )}
                              {aiImageUrls.length > 0 && (
                                <div
                                  data-testid="ai-home-ai-thumbnails"
                                  style={{
                                    display: 'flex',
                                    gap: 8,
                                    marginTop: aiText ? 8 : 0,
                                    overflowX: 'auto',
                                    paddingBottom: 2,
                                  }}
                                >
                                  {aiImageUrls.map((url, idx) => (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img
                                      key={`${url}-${idx}`}
                                      src={url}
                                      alt=""
                                      style={{
                                        width: 80,
                                        height: 80,
                                        borderRadius: 8,
                                        objectFit: 'cover',
                                        flexShrink: 0,
                                        cursor: 'pointer',
                                        border: '1px solid #EAEBED',
                                        background: '#F5F5F5',
                                      }}
                                      onClick={() => openAiHomeImageViewer(aiImageUrls, idx)}
                                      onError={(e) => {
                                        try {
                                          (e.currentTarget as HTMLImageElement).style.opacity = '0.4';
                                        } catch {}
                                      }}
                                    />
                                  ))}
                                </div>
                              )}
                            </>
                          );
                        })()
                      )}
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

                    {/* [PRD-440] AI 回答操作栏：提示文字 + 全宽虚线 + 渐变三图标（复制 / 转发 / 语音播报） */}
                    {showAiActions && (
                      <div data-testid="ai-home-ai-action-bar" style={{ marginTop: 12 }}>
                        <AiActionBar
                          ttsPlaying={ttsPlaying}
                          /* [BUG_FIX_AI_HOME_ACTIONBAR_AND_ATTACHMENT_FILTER_20260517 · Bug-2]
                           * 复制 / 语音播报内容也走 sanitize，避免把"内部协议提示语"
                           * 和图片 URL 文本带进剪贴板或 TTS 播报 */
                          onCopy={() => handleCopy(sanitizeAiContent(msg.content || ''))}
                          onShare={() => setShareOpen(true)}
                          onTts={() => handleTTS(sanitizeAiContent(msg.content || ''))}
                          disclaimer={disclaimerText}
                          disableToast
                        />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            {/* [PRD-433 F-11] Loading 卡片：白底+浅灰描边+88~90% 占屏，外部头像名称行保留 */}
            {sending && !messages.some(m => m.isStreaming) && (
              <div style={{ marginBottom: 24 }} data-testid="ai-home-ai-loading-card">
                {/* [PRD-449 R4] Loading 卡片小头像同步使用 AiAvatar 公共组件 */}
                <div className="flex items-center" style={{ marginBottom: 6, paddingLeft: 16 }}>
                  <AiAvatar
                    src={
                      aiHomeConfig.welcome?.avatar?.type === 'image'
                        ? aiHomeConfig.welcome?.avatar?.image_url
                        : aiHomeConfig.welcome?.avatar?.emoji
                    }
                    size={28}
                    shape="circle"
                    alt="AI 头像"
                    testId="ai-home-loading-avatar"
                  />
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
          [PRD-AIHOME-OPTIM-V1 2026-05-17 R1] 视觉优化：
            - 完全去掉底色和背景框，仅保留 🔔 图标本身
            - 初始垂直位置 = 顶部 banner 区域的垂直正中（由 bellInitialTop 测量得出）
            - 水平位置保持贴右（与原版一致）
            - 拖动后不持久化位置，离开页面再回来自动复位
          点击弹出"今日待办"抽屉（用药提醒 + 预约提醒） */}
      <SectionErrorBoundary name="floating_button">
        {floatingButtonVisible && (
          <ReminderBellButton
            initialTop={bellInitialTop}
            position={aiHomeConfig.floating_button?.position === 'left_bottom' ? 'left' : 'right'}
            badgeCount={reminderBadge}
            onClick={() => setReminderOpen(true)}
          />
        )}
      </SectionErrorBoundary>
      {/* [PRD-439 F-04~F-06] 今日待办抽屉 */}
      <SectionErrorBoundary name="reminder_drawer">
        <ReminderDrawer
          open={reminderOpen}
          onClose={() => {
            setReminderOpen(false);
            // 关闭后重置识药卡触发的咨询人筛选维度
            setReminderDrawerConsultantId(null);
            // [F10] 关闭后立刻重新计算红点（与顶部铃铛关闭一致逻辑）
            refreshReminderRedDot();
          }}
          onChangeBadge={() => {
            refreshReminderBadge();
            refreshReminderRedDot();
            // [PRD-BELL-UNIFIED-V1 2026-05-19] 通过事件总线让胶囊 / 其他订阅者同步刷新
            publishBellEvent('badge:refresh');
          }}
          consultantId={reminderDrawerConsultantId}
          onGoMedicationManage={() => {
            setReminderOpen(false);
            router.push('/ai-home/medication-plans');
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

      {/* [PRD-AICHAT-CAPSULE-V1 2026-05-15] AI 对话模式输入框上方胶囊条
          - 数据源：复用菜单模式的 /api/function-buttons?is_enabled=true（funcButtons）
          - 位置：输入框正上方，独立条带；数据为空 / 全部禁用 / 接口异常 → 不渲染
          - 键盘联动：textarea focus 时 isInputFocused=true → 整体隐藏
          - 点击：以"用户身份"自动发问（quick_ask 行为，复用 handleSend('preset')） */}
      <CapsuleBar
        // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 胶囊条数据源改为按 is_capsule 过滤（capsuleButtons）
        buttons={capsuleButtons.map((b) => ({
          id: b.id,
          name: b.name,
          icon: b.icon || '📌',
          button_type: b.button_type,
        }))}
        hidden={isInputFocused}
        onCapsuleClick={(cap) => {
          const full = capsuleButtons.find((b) => String(b.id) === String(cap.id))
            || funcButtons.find((b) => String(b.id) === String(cap.id));
          if (!full) return;
          handleCapsuleByType(full);
        }}
      />

      {/* [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 通用问卷抽屉
          [PRD-QUESTIONNAIRE-AUTONEXT-V1 2026-05-20] 透传按钮上的「自动下一步 / 每页题数」 */}
      <QuestionnaireDrawer
        open={qnDrawerOpen && !qnDrawerLoading && !!qnDrawerTemplate}
        onClose={() => setQnDrawerOpen(false)}
        template={qnDrawerTemplate}
        questions={qnDrawerQuestions}
        displayForm={qnDrawerDisplayForm}
        onSubmit={handleQuestionnaireDrawerSubmit}
        autoNextEnabled={
          qnDrawerButton
            ? (qnDrawerButton as any).auto_next_enabled === true
            : false
        }
        questionsPerPage={
          qnDrawerButton
            ? Math.max(1, Math.min(999, Number((qnDrawerButton as any).questions_per_page || 1)))
            : 1
        }
      />

      {/* [PRD-TAG-RECOMMEND-V1 2026-05-20] 推荐商品详情抽屉（drawer 模式） */}
      <RecommendGoodsDrawer
        open={recommendDrawerOpen}
        goods={recommendDrawerGoods}
        onClose={() => setRecommendDrawerOpen(false)}
      />

      {/* [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查抽屉 */}
      <HealthSelfCheckDrawer
        open={hscDrawerOpen}
        onClose={() => setHscDrawerOpen(false)}
        button={
          hscDrawerButton
            ? {
                id: Number(hscDrawerButton.id),
                name: hscDrawerButton.name,
                health_check_template_id: hscDrawerButton.health_check_template_id,
                archive_missing_strategy: hscDrawerButton.archive_missing_strategy,
                prompt_override_enabled: hscDrawerButton.prompt_override_enabled,
                prompt_override_text: hscDrawerButton.prompt_override_text,
              }
            : null
        }
        archive={
          selectedConsultant
            ? {
                id: selectedConsultant.id,
                name: selectedConsultant.nickname,
                age: null,
                gender: null,
                isDefault: false,
              }
            : { id: null, name: '本人', isDefault: true }
        }
        prefill={hscDrawerPrefill}
        onSubmit={handleHealthSelfCheckSubmit}
      />

      {/* [PRD-AICHAT-CAPSULE-V2 2026-05-15 需求 4.1] upload 胶囊触发的 ActionSheet（相册/拍照二选一） */}
      {capsuleUploadSheetOpen && (
        <div
          data-testid="capsule-upload-actionsheet"
          onClick={() => setCapsuleUploadSheetOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.45)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'center',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%',
              maxWidth: 760,
              background: '#fff',
              borderRadius: '16px 16px 0 0',
              padding: '12px 0 calc(8px + env(safe-area-inset-bottom))',
              boxShadow: '0 -2px 12px rgba(0,0,0,0.08)',
            }}
          >
            <button
              type="button"
              data-testid="capsule-upload-sheet-album"
              onClick={() => handleCapsuleUploadPick('album')}
              style={{
                width: '100%',
                padding: '14px 16px',
                background: 'transparent',
                border: 'none',
                borderBottom: '1px solid #F0F0F0',
                fontSize: 16,
                color: '#1F2937',
                cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              🖼️ 相册
            </button>
            <button
              type="button"
              data-testid="capsule-upload-sheet-camera"
              onClick={() => handleCapsuleUploadPick('camera')}
              style={{
                width: '100%',
                padding: '14px 16px',
                background: 'transparent',
                border: 'none',
                fontSize: 16,
                color: '#1F2937',
                cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              📷 拍照
            </button>
            <div style={{ height: 8, background: '#F5F5F7' }} />
            <button
              type="button"
              onClick={() => setCapsuleUploadSheetOpen(false)}
              style={{
                width: '100%',
                padding: '14px 16px',
                background: 'transparent',
                border: 'none',
                fontSize: 16,
                color: '#6B7280',
                cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* Input Bar */}
      {/* [PRD-AI-HOME-OPTIM-FINAL-V2 2026-05-19] 整条输入栏外层容器无背景色（透明），
          沿用页面本身底色，不做任何深底/渐变/灰底处理。 */}
      <div
        className="flex-shrink-0 px-4 py-3"
        style={{
          background: 'transparent',
          paddingBottom: 'calc(12px + env(safe-area-inset-bottom))',
        }}
      >
        {/* [PRD-426] 删除输入框上方"+ 选择咨询人"浮层（含其内嵌的 RecommendCards 推荐题），底部"为(XX)咨询 ⇄"作为唯一咨询人切换入口 */}

        {(() => {
          // [PRD-AI-HOME-OPTIM-FINAL-V2 2026-05-19]
          // ① placeholder 动态计算：`问答已结合【XX】的健康档案~`
          //    XX 取已选中咨询人的「关系」段；关系为空时降级为姓名；本人态 XX=「本人」。
          const consultantRelationOrName = (() => {
            if (!selectedConsultant) return '本人';
            const rel = (selectedConsultant.relation_type_name || selectedConsultant.relationship_type || '').trim();
            if (rel) return rel;
            const name = (selectedConsultant.nickname || '').trim();
            return name || '本人';
          })();
          const dynamicPlaceholder = `问答已结合【${consultantRelationOrName}】的健康档案~`;
          // ② 与「选中咨询人卡片」同款渐变（= --gradient-primary 同源）
          const PRIMARY_GRADIENT = 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)';
          // ③ 麦克风/键盘 圆形按钮统一样式：40x40 + 渐变蓝底 + 白色图标（复用 ./chat 的 SVG 资源，描边改白色）
          const ROUND_BTN_STYLE: React.CSSProperties = {
            background: PRIMARY_GRADIENT,
            border: 'none',
            boxShadow: '0 2px 8px rgba(2,132,199,0.25)',
            cursor: 'pointer',
            flexShrink: 0,
          };
          // 麦克风 SVG（复用 chat/[sessionId]/page.tsx 第 2715–2720 行，描边白色）
          const MicIcon = (
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#ffffff"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              data-testid="ai-home-mic-icon"
            >
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          );
          // 键盘 SVG（复用 chat/[sessionId]/page.tsx 第 2704–2713 行，描边白色）
          const KeyboardIcon = (
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#ffffff"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              data-testid="ai-home-keyboard-icon"
            >
              <rect x="2" y="4" width="20" height="16" rx="3" ry="3" />
              <line x1="6" y1="8" x2="6" y2="8" />
              <line x1="10" y1="8" x2="10" y2="8" />
              <line x1="14" y1="8" x2="14" y2="8" />
              <line x1="18" y1="8" x2="18" y2="8" />
              <line x1="6" y1="12" x2="6" y2="12" />
              <line x1="18" y1="12" x2="18" y2="12" />
              <line x1="8" y1="16" x2="16" y2="16" />
            </svg>
          );

          if (voiceMode && voiceSupported) {
            return (
              <div className="flex items-center gap-3">
                <button
                  className="w-10 h-10 flex items-center justify-center rounded-full"
                  style={ROUND_BTN_STYLE}
                  onClick={handleMicToggle}
                  aria-label="切换为键盘"
                  data-testid="ai-home-input-icon-btn"
                >
                  {KeyboardIcon}
                </button>
                <div
                  className="flex-1 flex items-center justify-center select-none"
                  style={{
                    height: 40,
                    borderRadius: 16,
                    background: recordCancelled && recording ? '#d32f2f' : '#0EA5E9',
                    color: '#fff',
                    fontSize: 14,
                    fontWeight: 500,
                    userSelect: 'none',
                    WebkitUserSelect: 'none',
                    touchAction: 'none',
                    transition: 'background 0.15s',
                  }}
                  onTouchStart={handleRecordTouchStart}
                  onTouchMove={handleRecordTouchMove}
                  onTouchEnd={handleRecordTouchEnd}
                  onMouseDown={() => startRecording()}
                  onMouseUp={() => { if (recordCancelled) cancelRecording(); else stopRecording(); }}
                  data-testid="ai-home-press-to-talk"
                >
                  {recording ? (recordCancelled ? '松开取消' : '松开结束') : '按住说话'}
                </div>
              </div>
            );
          }

          return (
            <div className="flex items-end gap-2" data-testid="ai-home-keyboard-bar">
              {voiceSupported && voiceInputVisible && (
                <button
                  className="w-10 h-10 flex items-center justify-center rounded-full mb-0"
                  style={ROUND_BTN_STYLE}
                  onClick={handleMicToggle}
                  aria-label="语音输入"
                  data-testid="ai-home-input-icon-btn"
                >
                  {MicIcon}
                </button>
              )}
              <div
                className="flex-1 flex items-end px-4 py-2"
                style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 24, minHeight: 44 }}
              >
                <textarea
                  ref={textareaRef}
                  className="flex-1 bg-transparent outline-none text-sm resize-none leading-6"
                  placeholder={dynamicPlaceholder}
                  value={inputValue}
                  onChange={handleTextareaInput}
                  onFocus={() => setIsInputFocused(true)}
                  onBlur={() => setIsInputFocused(false)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  rows={1}
                  style={{ color: THEME.textPrimary, maxHeight: 120, height: 24 }}
                  data-testid="ai-home-textarea"
                />
              </div>
              <button
                className="flex-shrink-0 flex items-center justify-center rounded-full text-sm font-medium mb-0"
                style={{
                  width: 44,
                  height: 44,
                  background: inputValue.trim() ? 'linear-gradient(135deg, #38BDF8, #0284C7)' : '#D1D5DB',
                  borderRadius: '50%',
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
          );
        })()}

        {/* v1.0 第二层：家庭成员快捷栏（家庭成员咨询胶囊 + 查看档案） */}
        {!voiceMode && (familyPillVisible || archiveLinkVisible) && (
          <div className="flex items-center justify-between gap-3 mt-2">
            {familyPillVisible ? (
              (() => {
                // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F13 2026-05-18]
                // AI 流式响应期间：胶囊置灰 + 右侧 loading 小图标 + 点击弹 Toast
                const isAiResponding = sending || messages.some((m) => m.isStreaming);
                return (
                  <button
                    data-testid="ai-home-consultant-pill"
                    data-disabled={isAiResponding ? '1' : '0'}
                    className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-full"
                    style={{
                      background: isAiResponding ? '#E5E7EB' : THEME.primaryLight,
                      color: isAiResponding ? '#9CA3AF' : THEME.primary,
                      fontSize: 12,
                      cursor: isAiResponding ? 'not-allowed' : 'pointer',
                      opacity: isAiResponding ? 0.75 : 1,
                    }}
                    onClick={() => {
                      if (isAiResponding) {
                        try {
                          Toast.show({ content: 'AI 正在回答中，请稍候再切换咨询人', position: 'bottom' });
                        } catch {}
                        return;
                      }
                      setConsultantOpen(true);
                    }}
                    aria-label="切换咨询对象"
                  >
                    <span>{renderFamilyPillText()}</span>
                    {isAiResponding ? (
                      <span
                        data-testid="ai-home-consultant-pill-loading"
                        aria-label="AI 正在回答"
                        style={{
                          width: 12,
                          height: 12,
                          border: '1.5px solid #9CA3AF',
                          borderTopColor: 'transparent',
                          borderRadius: '50%',
                          animation: 'aihomeConsultPillSpin 0.85s linear infinite',
                          display: 'inline-block',
                          marginLeft: 4,
                        }}
                      />
                    ) : (
                      <span style={{ fontSize: 10 }}>⇆</span>
                    )}
                    <style>{`@keyframes aihomeConsultPillSpin{to{transform:rotate(360deg)}}`}</style>
                  </button>
                );
              })()
            ) : <div />}
            {archiveLinkVisible && (
              <button
                className="flex-shrink-0 text-xs"
                style={{ color: THEME.textSecondary }}
                onClick={() => {
                  const p = aiHomeConfig.input?.family_consult?.archive_path || '/health-profile';
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
        onScan={handleScan}
        onFontSize={handleFontSize}
        onShare={() => setShareOpen(true)}
        // [Bug 修复 v1.2 §11.1] 会员中心入口：跳转 H5 会员中心页面（自动锚定到本月配额板块）
        onMemberCenter={() => { setMoreMenuOpen(false); router.push('/member-center#quota'); }}
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

      {/* [M1] 蓝色横条撤销提示已移除 */}

      {/* [PRD-AI-HOME-OPTIM-V4 M2 · F-切人-01] 中央 Toast 浮层（屏幕中央偏上 20%，2 秒自动消失） */}
      {centerToastVisible && (
        <div
          style={{
            position: 'fixed',
            top: '20%',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 1100,
            background: 'rgba(46, 46, 46, 0.85)',
            color: '#fff',
            padding: '10px 18px',
            borderRadius: 22,
            fontSize: 14,
            lineHeight: 1.4,
            maxWidth: '80%',
            textAlign: 'center',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            pointerEvents: 'none',
            animation: 'aihomev4-toast-fade 200ms ease-out',
          }}
          data-testid="consult-switch-center-toast"
        >
          {centerToastText}
        </div>
      )}

      {/* [PRD-AI-HOME-OPTIM-V4 M3 · F-悬浮-01] 右下角小康头像悬浮球（F 款） */}
      <div
        style={{
          position: 'fixed',
          right: 16,
          bottom: 96,
          zIndex: 1050,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          pointerEvents: 'none',
        }}
      >
        {/* 首次引导气泡 */}
        {floatingFirstGuideVisible && (
          <div
            style={{
              marginBottom: 8,
              marginRight: 4,
              background: '#fff',
              color: '#2E2E2E',
              fontSize: 12,
              padding: '6px 10px',
              borderRadius: 12,
              boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
              border: '1px solid #E5F4FF',
              pointerEvents: 'auto',
              maxWidth: 200,
              animation: 'aihomev4-toast-fade 200ms ease-out',
            }}
            data-testid="floating-ball-first-guide"
          >
            健康服务入口在这里，随时点开
          </div>
        )}
        {/* 悬浮球本体 */}
        <button
          type="button"
          onClick={handleFloatingBallClick}
          aria-label="健康服务入口"
          data-testid="floating-ball"
          style={{
            width: 48,
            height: 48,
            borderRadius: '50%',
            border: '2px solid #0EA5E9',
            background: 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(0,0,0,0.16)',
            padding: 0,
            pointerEvents: 'auto',
            animation: floatingPanelOpen ? 'none' : 'aihomev4-floating-ball-breath 2.4s ease-in-out infinite',
            color: '#fff',
            fontSize: 22,
            fontWeight: 700,
            lineHeight: 1,
            fontFamily: 'system-ui, -apple-system, "PingFang SC", "Helvetica Neue", sans-serif',
          }}
        >
          <span aria-hidden="true">康</span>
        </button>
      </div>

      {/* [PRD-AI-HOME-OPTIM-V4 M3 · F-悬浮-03] 展开面板（复刻顶部欢迎语 + 4 入口 + 今日用药） */}
      {floatingPanelOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1080,
            background: 'rgba(0,0,0,0.35)',
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'center',
            animation: 'aihomev4-toast-fade 200ms ease-out',
          }}
          onClick={() => setFloatingPanelOpen(false)}
          data-testid="floating-ball-panel-mask"
        >
          <div
            style={{
              width: '100%',
              maxWidth: 480,
              background: '#fff',
              borderTopLeftRadius: 20,
              borderTopRightRadius: 20,
              padding: '20px 16px 24px',
              maxHeight: '70vh',
              overflowY: 'auto',
              transformOrigin: 'bottom right',
              animation: 'aihomev4-panel-zoom-in 200ms ease-out',
            }}
            onClick={(e) => e.stopPropagation()}
            data-testid="floating-ball-panel"
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ fontWeight: 600, fontSize: 16, color: '#1F2937' }}>
                {selectedConsultant
                  ? `现在为 ${selectedConsultant.nickname} 服务`
                  : '欢迎您！我是您的 AI 健康顾问小康'}
              </div>
              <button
                type="button"
                onClick={() => setFloatingPanelOpen(false)}
                aria-label="关闭"
                style={{
                  background: 'transparent',
                  border: 'none',
                  fontSize: 22,
                  color: '#9CA3AF',
                  cursor: 'pointer',
                  padding: 4,
                  lineHeight: 1,
                }}
              >
                ×
              </button>
            </div>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 16 }}>
              健康服务入口，随时为您和家人提供专业的健康咨询
            </div>

            {/* 4 个功能入口（复刻顶部宫格的前 4 个） */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 8,
                marginBottom: 16,
              }}
              data-testid="floating-ball-panel-grid"
            >
              {(funcButtons || []).slice(0, 4).map((btn) => (
                <button
                  type="button"
                  key={btn.id}
                  onClick={() => {
                    try {
                      api.post('/api/ai-home/track', {
                        event: 'floating_ball_panel_action',
                        platform: 'h5',
                        payload: { entry_name: btn.name || String(btn.id) },
                      }).catch(() => {});
                    } catch {}
                    setFloatingPanelOpen(false);
                    handleFunctionButtonClick(btn);
                  }}
                  style={{
                    background: '#F0F9FF',
                    border: '1px solid #E0F2FE',
                    borderRadius: 12,
                    padding: '10px 4px',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 4,
                    minHeight: 70,
                  }}
                >
                  <span style={{ fontSize: 24, lineHeight: 1 }} aria-hidden="true">
                    {btn.icon || '🩺'}
                  </span>
                  <span style={{ fontSize: 12, color: '#0F172A', textAlign: 'center', lineHeight: 1.2 }}>
                    {btn.name || '健康服务'}
                  </span>
                </button>
              ))}
              {(!funcButtons || funcButtons.length === 0) && (
                <div style={{ gridColumn: '1 / -1', textAlign: 'center', fontSize: 12, color: '#94A3B8' }}>
                  健康服务正在加载…
                </div>
              )}
            </div>

            {/* 今日用药卡片（轻量化展示） */}
            <div
              style={{
                background: 'linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 100%)',
                borderRadius: 12,
                padding: '14px 12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                cursor: 'pointer',
              }}
              onClick={() => {
                setFloatingPanelOpen(false);
                router.push('/ai-home/medication-reminder');
              }}
              data-testid="floating-ball-panel-medication"
            >
              <div>
                <div style={{ fontSize: 14, color: '#0F172A', fontWeight: 500 }}>今日用药</div>
                <div style={{ fontSize: 12, color: '#475569', marginTop: 2 }}>
                  查看{selectedConsultant ? selectedConsultant.nickname : '本人'}的今日用药提醒
                </div>
              </div>
              <span style={{ color: '#0284C7', fontSize: 20 }} aria-hidden="true">›</span>
            </div>
          </div>
        </div>
      )}

      {/* [PRD-AI-HOME-OPTIM-V4] 全局动画 */}
      <style jsx global>{`
        @keyframes aihomev4-toast-fade {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes aihomev4-floating-ball-breath {
          0%, 100% { box-shadow: 0 4px 12px rgba(0,0,0,0.16), 0 0 0 0 rgba(14, 165, 233, 0.45); }
          50% { box-shadow: 0 4px 12px rgba(0,0,0,0.16), 0 0 0 8px rgba(14, 165, 233, 0); }
        }
        @keyframes aihomev4-panel-zoom-in {
          from { transform: scale(0.92); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }
      `}</style>

      {/* [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 加入用药计划抽屉 */}
      <AddMedicationDrawer
        open={addMedDrawerOpen}
        card={activeDrugCard || { drug_name: '' }}
        familyMemberId={selectedConsultant?.id ?? null}
        consultantName={selectedConsultant?.nickname || null}
        isSelf={!selectedConsultant}
        onClose={() => setAddMedDrawerOpen(false)}
        onSaved={() => {
          // 保存成功后：本地立即标记 added=true（按 drugAddedMap） + 触发批量刷新
          const dn = activeDrugCard?.drug_name || '';
          const cid = selectedConsultant?.id ?? 0;
          if (dn) {
            setDrugAddedMap((prev) => ({ ...prev, [`${cid}|${dn}`]: true }));
          }
          // 兼容旧字段：同时把消息 drugMeta.added_to_plan 也写 true
          if (activeDrugMsgId) {
            setMessages((prev) => prev.map((m) =>
              m.id === activeDrugMsgId
                ? { ...m, drugMeta: { ...(m.drugMeta || {}), added_to_plan: true } as any }
                : m,
            ));
          }
          // [PRD-AI-HOME-OPTIM-FINAL-V1 2026-05-19 §1.6.1]
          // 新增 1.5s 轻量 Toast：「已加入用药计划」
          try {
            Toast.show({ content: '已加入用药计划', position: 'top', duration: 1500 });
          } catch {}
          // 异步重刷一次以校准
          refreshDrugAddedStatus([dn]).catch(() => {});
          // 新加入计划后立即刷新"今日用药"红点 / 置灰状态
          refreshReminderRedDot().catch(() => {});
          // 关闭抽屉
          setAddMedDrawerOpen(false);
        }}
      />

      {/* [PRD-MED-PLAN-INTERACT-OPTIM-V1 2026-05-18 §3.1.2] 重新拍照选择抽屉 */}
      <RetakePhotoDrawer
        open={retakeDrawerOpen}
        onClose={() => setRetakeDrawerOpen(false)}
        onPicked={async (file) => {
          // 上传图片 + 走识药 SSE 流程
          try {
            Toast.show({ icon: 'loading', content: '识别中…', duration: 0 });
            const url = await uploadImageToServer(file);
            try { Toast.clear(); } catch {}

            // 启动识别失败兜底定时器：60s 内未拿到识药卡片或重拍消息 → 视为失败
            if (recogTimerRef.current) clearTimeout(recogTimerRef.current);
            recogTimerRef.current = setTimeout(() => {
              setRecogFailDrawerOpen(true);
            }, 60000);

            // 通过和拍照按钮一致的接口触发 SSE：传 image url + 识药 intent
            handleSend('我上传了一张药品图片，请帮我识别', 'preset', {
              suppressUserBubble: true,
              backendText: `[用户上传的图片 1 张]\n1. ${url}\n\n我上传了一张药品图片，请帮我识别`,
              sseExtras: {
                intent: 'drug_identify',
                imageUrls: [url],
                buttonType: 'drug_identify',
                buttonId: null,
              },
            } as any);
          } catch {
            try { Toast.clear(); } catch {}
            // 上传失败 → 直接弹失败抽屉
            setRecogFailDrawerOpen(true);
          }
        }}
      />

      {/* [PRD-MED-PLAN-INTERACT-OPTIM-V1 2026-05-18 §3.1.3-3.1.4] 识别失败抽屉（含手动录入滑动切换） */}
      <RecognizeFailDrawer
        open={recogFailDrawerOpen}
        onClose={() => setRecogFailDrawerOpen(false)}
        onRetry={() => {
          setRecogFailDrawerOpen(false);
          setRetakeDrawerOpen(true);
        }}
        familyMemberId={selectedConsultant?.id ?? null}
        onSaved={() => {
          // 手动录入保存成功 → 关闭抽屉 + 刷新识药卡片状态
          setRecogFailDrawerOpen(false);
          const names: string[] = [];
          for (const m of messages) {
            if (
              m.drugMeta &&
              m.drugMeta.message_type === 'drug_identify_card' &&
              Array.isArray(m.drugMeta.medicines)
            ) {
              const n =
                m.drugMeta.medicines[0]?.name ||
                m.drugMeta.medicines[0]?.brand ||
                '';
              if (n) names.push(n);
            }
          }
          if (names.length) refreshDrugAddedStatus(names).catch(() => {});
        }}
      />

      {/* [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 查看用药计划抽屉 */}
      <ViewMedicationPlansDrawer
        open={viewMedDrawerOpen}
        familyMemberId={selectedConsultant?.id ?? null}
        consultantName={selectedConsultant?.nickname || null}
        isSelf={!selectedConsultant}
        onClose={() => setViewMedDrawerOpen(false)}
        onGoAdd={() => {
          // 空态「去新增」：关查看 → 开加入
          setAddMedDrawerOpen(true);
        }}
        onChanged={() => {
          // 列表中条目编辑/删除后重新刷新所有识药卡片状态
          const names: string[] = [];
          for (const m of messages) {
            if (
              m.drugMeta &&
              m.drugMeta.message_type === 'drug_identify_card' &&
              Array.isArray(m.drugMeta.medicines)
            ) {
              const n =
                m.drugMeta.medicines[0]?.name ||
                m.drugMeta.medicines[0]?.brand ||
                '';
              if (n) names.push(n);
            }
          }
          if (names.length) refreshDrugAddedStatus(names);
        }}
      />

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
    </div>
  );
}
