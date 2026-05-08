'use client';

import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import {
  Card,
  Typography,
  Button,
  Space,
  Input,
  Switch,
  Select,
  Form,
  message,
  Spin,
  Upload,
  Radio,
  InputNumber,
  Modal,
  Empty,
  Divider,
  Alert,
  Tabs,
  Row,
  Col,
  Tooltip,
  Badge,
} from 'antd';
import type { UploadProps } from 'antd';
import {
  SaveOutlined,
  ReloadOutlined,
  HistoryOutlined,
  PlusOutlined,
  DeleteOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { get, put, patch, post } from '@/lib/api';
import { useRouter } from 'next/navigation';

const { Title, Text, Paragraph } = Typography;

// ──────────────── 类型定义（保持与后端 schema 对齐） ────────────────

type AvatarObj = { type: 'emoji' | 'image'; emoji?: string; image_url?: string };
type RecommendedQ = {
  id: string;
  icon: string;
  icon_image_url?: string;
  title: string;
  question: string;
  enabled: boolean;
  sort: number;
};
type FuncGridItem = {
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
};
type SessionStrategy = {
  max_answer_chars: number;
  show_loading: boolean;
  daily_free_quota: number;
  answer_style: 'professional' | 'easy' | 'friendly';
  sensitive_filter: boolean;
  context_memory_rounds: 3 | 5 | 10 | 20;
  disclaimer: string;
};
type GlobalSwitches = {
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
type Cfg = {
  welcome: {
    avatar: AvatarObj;
    greetings: { morning: string[]; afternoon: string[]; evening: string[] };
    subtitles: string[];
    show_nickname: boolean;
    main_title: string;
    sub_title: string;
  };
  topbar: {
    title: string;
    logo: AvatarObj;
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
    strategy: SessionStrategy;
  };
  floating_button: {
    enabled: boolean;
    icon: string;
    icon_image_url?: string;
    label?: string;
    show_label: boolean;
    target_path: string;
    position: 'right_bottom' | 'left_bottom';
  };
  banner: { visible: boolean };
  health_tips: { visible: boolean; interval_seconds: number; show_indicator: boolean };
  func_grid: { visible: boolean; columns: 2 | 3 | 4; max_count: number; items: FuncGridItem[] };
  quick_tags: { visible: boolean; max_count: number };
  recommended_questions: RecommendedQ[];
  empty_placeholder: { icon: string; icon_image_url?: string; main_title: string };
  global_switches: GlobalSwitches;
  // PRD-414 v1.1：AI 对话页（chat）配置
  ai_chat: {
    avatar: AvatarObj;
    signature: string;
    profile_row_enabled: boolean;
    profile_row_template: string;
    punchcard_draggable: boolean;
    scroll_to_bottom_button: boolean;
    sticky_topbar: boolean;
    history_retention_days: number;
  };
};

const DEFAULT_CFG: Cfg = {
  welcome: {
    avatar: { type: 'emoji', emoji: '🌿' },
    greetings: { morning: ['早上好'], afternoon: ['午安'], evening: ['晚上好'] },
    subtitles: ['有什么健康问题想问我?'],
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
  ],
  empty_placeholder: { icon: '💬', main_title: '还没有对话记录' },
  ai_chat: {
    avatar: { type: 'emoji', emoji: '🌿', image_url: '' },
    signature: '小康',
    profile_row_enabled: true,
    profile_row_template: '本次回答结合 {name} 的档案',
    punchcard_draggable: true,
    scroll_to_bottom_button: true,
    sticky_topbar: true,
    history_retention_days: 0,
  },
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

// ──────────────── Tab 元信息 ────────────────

type TabKey = 'welcome' | 'first_screen' | 'func_grid' | 'input' | 'session' | 'global';

const TAB_META: { key: TabKey; label: string }[] = [
  { key: 'welcome', label: '欢迎区' },
  { key: 'first_screen', label: '首屏内容' },
  { key: 'func_grid', label: '功能宫格' },
  { key: 'input', label: '输入栏' },
  { key: 'session', label: '会话策略' },
  { key: 'global', label: '全局开关' },
];

// 每个 Tab 涉及哪些 Cfg 顶层模块字段（用来比较 dirty 与生成保存请求）
const TAB_MODULES: Record<TabKey, (keyof Cfg)[]> = {
  welcome: ['welcome'],
  first_screen: ['health_tips', 'empty_placeholder', 'recommended_questions'],
  func_grid: ['func_grid'],
  input: ['input'],
  session: ['session'],
  // PRD-414 v1.1：ai_chat 模块作为"AI 对话页"配置归入全局开关 Tab
  global: ['global_switches', 'floating_button', 'topbar', 'ai_chat'],
};

// ──────────────── 通用工具：深拷贝 + 深比较 ────────────────

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v));
}
function deepEqual(a: any, b: any): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

// ──────────────── 字符串数组编辑器 ────────────────

function StringListEditor({
  value,
  onChange,
  max = 20,
  placeholder = '输入文本',
}: {
  value: string[];
  onChange: (v: string[]) => void;
  max?: number;
  placeholder?: string;
}) {
  const list = Array.isArray(value) ? value : [];
  return (
    <div>
      {list.map((item, idx) => (
        <Space.Compact key={idx} style={{ display: 'flex', marginBottom: 6 }}>
          <Input
            value={item}
            onChange={(e) => {
              const next = [...list];
              next[idx] = e.target.value;
              onChange(next);
            }}
            placeholder={placeholder}
          />
          <Button
            danger
            icon={<DeleteOutlined />}
            disabled={list.length <= 1}
            onClick={() => onChange(list.filter((_, i) => i !== idx))}
          />
        </Space.Compact>
      ))}
      {list.length < max && (
        <Button
          icon={<PlusOutlined />}
          onClick={() => onChange([...list, ''])}
          size="small"
        >
          新增一条
        </Button>
      )}
      <Text type="secondary" style={{ marginLeft: 8 }}>
        ({list.length}/{max})
      </Text>
    </div>
  );
}

// ──────────────── 头像/Logo 编辑器 ────────────────

function AvatarEditor({
  value,
  onChange,
  uploadAction,
}: {
  value: AvatarObj;
  onChange: (v: AvatarObj) => void;
  uploadAction: (file: File) => Promise<string | null>;
}) {
  const v = value || { type: 'emoji', emoji: '🌿' };
  const uploadProps: UploadProps = {
    showUploadList: false,
    beforeUpload: async (file) => {
      const url = await uploadAction(file as File);
      if (url) {
        onChange({ ...v, type: 'image', image_url: url });
      }
      return false;
    },
    accept: 'image/png,image/jpeg,image/jpg,image/webp',
  };
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Radio.Group
        value={v.type}
        onChange={(e) => onChange({ ...v, type: e.target.value })}
      >
        <Radio value="emoji">使用 Emoji</Radio>
        <Radio value="image">使用图片</Radio>
      </Radio.Group>
      {v.type === 'emoji' ? (
        <Input
          value={v.emoji || ''}
          onChange={(e) => onChange({ ...v, emoji: e.target.value })}
          maxLength={4}
          placeholder="输入 emoji，例如 🌿"
          style={{ width: 200 }}
        />
      ) : (
        <Space>
          {v.image_url ? (
            <img
              src={v.image_url}
              alt="预览"
              style={{ width: 64, height: 64, borderRadius: 8, objectFit: 'cover', border: '1px solid #eee' }}
            />
          ) : (
            <div
              style={{ width: 64, height: 64, borderRadius: 8, background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#aaa' }}
            >
              暂无
            </div>
          )}
          <Upload {...uploadProps}>
            <Button icon={<UploadOutlined />}>上传图片（≤1MB, 1:1）</Button>
          </Upload>
        </Space>
      )}
    </Space>
  );
}

// ──────────────── 主页面 ────────────────

export default function AIHomeConfigPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // baseline = 上次成功保存或刚加载的"权威值"，用于重置和 dirty 判断
  const [baseline, setBaseline] = useState<Cfg>(DEFAULT_CFG);
  // draft = 当前正在编辑的值
  const [draft, setDraft] = useState<Cfg>(DEFAULT_CFG);
  const [activeTab, setActiveTab] = useState<TabKey>('welcome');

  // 字段错误集合：'welcome.main_title' => '主标题不能为空'
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // 辅助：判断指定 Tab 是否 dirty
  const isTabDirty = useCallback(
    (tab: TabKey): boolean => {
      return TAB_MODULES[tab].some((m) => !deepEqual((draft as any)[m], (baseline as any)[m]));
    },
    [draft, baseline]
  );

  const dirtyMap = useMemo(() => {
    const m = {} as Record<TabKey, boolean>;
    TAB_META.forEach((t) => {
      m[t.key] = isTabDirty(t.key);
    });
    return m;
  }, [isTabDirty]);

  const currentTabDirty = dirtyMap[activeTab];

  // ──────────────── 数据加载 ────────────────

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<{ config: Cfg }>('/api/admin/ai-home-config');
      const merged = { ...DEFAULT_CFG, ...(res.config || {}) } as Cfg;
      setBaseline(clone(merged));
      setDraft(clone(merged));
      setFieldErrors({});
    } catch {
      message.error('加载配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // ──────────────── 图片上传 ────────────────

  const upload = async (file: File): Promise<string | null> => {
    if (file.size > 1024 * 1024) {
      message.error('图片不能超过 1MB');
      return null;
    }
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await post<{ url: string }>(
        '/api/admin/ai-home-config/upload-image',
        fd,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      message.success('上传成功');
      return res.url;
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '上传失败');
      return null;
    }
  };

  // ──────────────── Tab 字段校验（提交级强校验，按 PRD F-12） ────────────────

  function validateTab(tab: TabKey, cfg: Cfg): Record<string, string> {
    const errs: Record<string, string> = {};
    if (tab === 'welcome') {
      if (!cfg.welcome.main_title || cfg.welcome.main_title.length > 30) {
        errs['welcome.main_title'] = '主标题为必填且不超过30字';
      }
      if (cfg.welcome.sub_title && cfg.welcome.sub_title.length > 50) {
        errs['welcome.sub_title'] = '副标题不超过50字';
      }
    }
    if (tab === 'first_screen') {
      const sec = cfg.health_tips.interval_seconds;
      if (!sec || sec < 3 || sec > 5) {
        errs['health_tips.interval_seconds'] = '轮播间隔须在 3~5 秒';
      }
      if (cfg.empty_placeholder.main_title && cfg.empty_placeholder.main_title.length > 20) {
        errs['empty_placeholder.main_title'] = '空对话主标题不超过20字';
      }
      cfg.recommended_questions.forEach((q, i) => {
        if (q.title && q.title.length > 8) {
          errs[`recommended_questions.${i}.title`] = '推荐问标题不超过8字';
        }
        if (q.question && q.question.length > 200) {
          errs[`recommended_questions.${i}.question`] = '推荐问内容不超过200字';
        }
      });
    }
    if (tab === 'func_grid') {
      const items = cfg.func_grid.items;
      if (items.length < 1 || items.length > 6) {
        errs['func_grid.items'] = '功能宫格须有 1~6 项';
      }
      const hex = /^#[0-9A-Fa-f]{6}$/;
      items.forEach((it, i) => {
        if (!it.main_text || it.main_text.length > 8) {
          errs[`func_grid.items.${i}.main_text`] = '主文案为必填且不超过8字';
        }
        if (it.sub_text && it.sub_text.length > 12) {
          errs[`func_grid.items.${i}.sub_text`] = '副说明不超过12字';
        }
        if (!hex.test(it.gradient_start)) {
          errs[`func_grid.items.${i}.gradient_start`] = '起始色须为合法 HEX，如 #5B6CFF';
        }
        if (!hex.test(it.gradient_end)) {
          errs[`func_grid.items.${i}.gradient_end`] = '结束色须为合法 HEX，如 #8B9AFF';
        }
      });
    }
    if (tab === 'input') {
      if (cfg.input.family_consult.enabled && !cfg.input.family_consult.template.includes('{name}')) {
        errs['input.family_consult.template'] = '模板必须包含 {name} 占位符';
      }
    }
    if (tab === 'session') {
      const s = cfg.session.strategy;
      if (s.max_answer_chars < 100 || s.max_answer_chars > 5000) {
        errs['session.strategy.max_answer_chars'] = '回答字数须在 100~5000';
      }
      if (s.daily_free_quota < 1 || s.daily_free_quota > 999) {
        errs['session.strategy.daily_free_quota'] = '免费次数须在 1~999';
      }
      if (s.disclaimer && s.disclaimer.length > 100) {
        errs['session.strategy.disclaimer'] = '免责声明不超过100字';
      }
    }
    if (tab === 'global') {
      // PRD-414 v1.1：ai_chat 模块字段校验
      const ac = cfg.ai_chat;
      if (!ac.signature || ac.signature.length > 10) {
        errs['ai_chat.signature'] = 'AI 署名为必填且不超过10字';
      }
      if (!ac.profile_row_template || !ac.profile_row_template.includes('{name}')) {
        errs['ai_chat.profile_row_template'] = '档案行模板必须包含 {name} 占位符';
      }
      if (ac.profile_row_template && ac.profile_row_template.length > 30) {
        errs['ai_chat.profile_row_template'] = '档案行模板不超过30字';
      }
      if (ac.history_retention_days < 0 || ac.history_retention_days > 3650) {
        errs['ai_chat.history_retention_days'] = '历史保留天数须在 0~3650（0=永久）';
      }
    }
    return errs;
  }

  // ──────────────── 单 Tab 保存（按 PRD 推荐每模块独立 PATCH） ────────────────

  const saveTab = useCallback(
    async (tab: TabKey): Promise<boolean> => {
      const errs = validateTab(tab, draft);
      if (Object.keys(errs).length > 0) {
        setFieldErrors(errs);
        const firstKey = Object.keys(errs)[0];
        message.error(`字段「${firstKey}」校验未通过：${errs[firstKey]}`);
        // 滚动到第一个错误字段
        setTimeout(() => {
          const el = document.querySelector(`[data-field-key="${firstKey}"]`);
          if (el && (el as HTMLElement).scrollIntoView) {
            (el as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 50);
        return false;
      }
      setSaving(true);
      try {
        // 顺序 PATCH 各模块（保证日志按顺序写入）
        let latest: Cfg | null = null;
        for (const mod of TAB_MODULES[tab]) {
          const res = await patch<{ config: Cfg }>(
            `/api/admin/ai-home-config/${mod}`,
            { data: (draft as any)[mod] }
          );
          latest = { ...DEFAULT_CFG, ...(res.config || {}) } as Cfg;
        }
        if (latest) {
          setBaseline(clone(latest));
          setDraft(clone(latest));
        }
        setFieldErrors({});
        message.success({ content: '保存成功', duration: 2 });
        return true;
      } catch (e: any) {
        message.error(`保存失败：${e?.response?.data?.detail || '后端返回异常'}`);
        return false;
      } finally {
        setSaving(false);
      }
    },
    [draft]
  );

  // ──────────────── 单 Tab 重置（带二次确认） ────────────────

  const resetTab = useCallback(
    (tab: TabKey) => {
      if (!isTabDirty(tab)) return;
      Modal.confirm({
        title: '确认重置',
        content: '确定要放弃当前修改并恢复为上次保存的值吗？',
        okText: '确认重置',
        okType: 'danger',
        cancelText: '取消',
        onOk: () => {
          const next = clone(draft);
          for (const mod of TAB_MODULES[tab]) {
            (next as any)[mod] = clone((baseline as any)[mod]);
          }
          setDraft(next);
          // 清掉本 Tab 相关的字段错误
          setFieldErrors((prev) => {
            const out: Record<string, string> = {};
            const prefixes = TAB_MODULES[tab].map((m) => String(m));
            for (const [k, v] of Object.entries(prev)) {
              if (!prefixes.some((p) => k.startsWith(p))) out[k] = v;
            }
            return out;
          });
        },
      });
    },
    [draft, baseline, isTabDirty]
  );

  // ──────────────── 切 Tab 拦截：未保存改动时弹三选确认框（受控 Modal） ────────────────

  const [pendingTargetTab, setPendingTargetTab] = useState<TabKey | null>(null);

  const trySwitchTab = useCallback(
    (target: TabKey) => {
      if (target === activeTab) return;
      if (!isTabDirty(activeTab)) {
        setActiveTab(target);
        return;
      }
      setPendingTargetTab(target);
    },
    [activeTab, isTabDirty]
  );

  const handleConfirmSaveAndSwitch = async () => {
    const target = pendingTargetTab;
    if (!target) return;
    const ok = await saveTab(activeTab);
    if (ok) {
      setPendingTargetTab(null);
      setActiveTab(target);
    }
    // 保存失败则停留在当前 Tab，不关闭弹窗用户可点取消
  };

  const handleDiscardAndSwitch = () => {
    const target = pendingTargetTab;
    if (!target) return;
    const next = clone(draft);
    for (const mod of TAB_MODULES[activeTab]) {
      (next as any)[mod] = clone((baseline as any)[mod]);
    }
    setDraft(next);
    setFieldErrors((prev) => {
      const out: Record<string, string> = {};
      const prefixes = TAB_MODULES[activeTab].map((m) => String(m));
      for (const [k, v] of Object.entries(prev)) {
        if (!prefixes.some((p) => k.startsWith(p))) out[k] = v;
      }
      return out;
    });
    setPendingTargetTab(null);
    setActiveTab(target);
  };

  const handleCancelSwitch = () => {
    setPendingTargetTab(null);
  };

  // ──────────────── 草稿更新工具：各 Tab 内部用 ────────────────

  const update = (mut: (d: Cfg) => void) => {
    const next = clone(draft);
    mut(next);
    setDraft(next);
  };

  // 包装 Form.Item，自动注入 validateStatus / help / data-field-key
  const FieldItem = (props: { fieldKey: string; label: React.ReactNode; extra?: React.ReactNode; tooltip?: string; children: React.ReactNode }) => {
    const err = fieldErrors[props.fieldKey];
    const node = (
      <Form.Item
        label={props.label}
        extra={props.extra}
        tooltip={props.tooltip}
        validateStatus={err ? 'error' : undefined}
        help={err}
      >
        <div data-field-key={props.fieldKey}>{props.children}</div>
      </Form.Item>
    );
    return node;
  };

  // ──────────────── 推荐问相关操作 ────────────────

  const updateRQ = (idx: number, patchObj: Partial<RecommendedQ>) => {
    update((d) => {
      d.recommended_questions[idx] = { ...d.recommended_questions[idx], ...patchObj };
    });
  };
  const addRQ = () => {
    if (draft.recommended_questions.length >= 20) {
      message.warning('最多 20 条');
      return;
    }
    update((d) => {
      d.recommended_questions.push({
        id: '',
        icon: '💡',
        title: '新推荐问',
        question: '',
        enabled: true,
        sort: (d.recommended_questions[d.recommended_questions.length - 1]?.sort ?? 0) + 1,
      });
    });
  };
  const removeRQ = (idx: number) => {
    update((d) => {
      d.recommended_questions.splice(idx, 1);
    });
  };
  const moveRQ = (idx: number, delta: number) => {
    update((d) => {
      const target = idx + delta;
      if (target < 0 || target >= d.recommended_questions.length) return;
      [d.recommended_questions[idx], d.recommended_questions[target]] = [d.recommended_questions[target], d.recommended_questions[idx]];
      d.recommended_questions.forEach((it, i) => { it.sort = i + 1; });
    });
  };

  // ──────────────── 各 Tab 渲染函数 ────────────────

  const renderWelcomeTab = () => (
    <Card>
      <Form layout="vertical">
        <FieldItem fieldKey="welcome.main_title" label="主标题（首页大字，≤30字）" tooltip="支持 {昵称} 占位符，自动替换为用户昵称">
          <Input
            value={draft.welcome.main_title}
            maxLength={30}
            showCount
            onChange={(e) => update((d) => { d.welcome.main_title = e.target.value; })}
            placeholder="早上好，{昵称}！"
          />
        </FieldItem>
        <FieldItem fieldKey="welcome.sub_title" label="副标题（≤50字）">
          <Input
            value={draft.welcome.sub_title}
            maxLength={50}
            showCount
            onChange={(e) => update((d) => { d.welcome.sub_title = e.target.value; })}
            placeholder="我是您的AI健康顾问小康"
          />
        </FieldItem>
        <Form.Item label="头像">
          <AvatarEditor
            value={draft.welcome.avatar}
            onChange={(v) => update((d) => { d.welcome.avatar = v; })}
            uploadAction={upload}
          />
        </Form.Item>
        <Divider plain>多条问候语随机抽 1（兼容旧版本）</Divider>
        <Form.Item label="早上问候语 (05:00-12:00)">
          <StringListEditor
            value={draft.welcome.greetings.morning}
            onChange={(v) => update((d) => { d.welcome.greetings.morning = v; })}
            placeholder="例如：早上好"
          />
        </Form.Item>
        <Form.Item label="下午问候语 (12:00-18:00)">
          <StringListEditor
            value={draft.welcome.greetings.afternoon}
            onChange={(v) => update((d) => { d.welcome.greetings.afternoon = v; })}
            placeholder="例如：午安"
          />
        </Form.Item>
        <Form.Item label="晚上问候语 (18:00-次日 05:00)">
          <StringListEditor
            value={draft.welcome.greetings.evening}
            onChange={(v) => update((d) => { d.welcome.greetings.evening = v; })}
            placeholder="例如：晚上好"
          />
        </Form.Item>
        <Form.Item label="副标题（多条随机抽 1）">
          <StringListEditor
            value={draft.welcome.subtitles}
            onChange={(v) => update((d) => { d.welcome.subtitles = v; })}
            placeholder="例如：有什么健康问题想问我?"
          />
        </Form.Item>
        <Form.Item label="是否在问候语后拼接用户昵称">
          <Switch
            checked={draft.welcome.show_nickname}
            onChange={(c) => update((d) => { d.welcome.show_nickname = c; })}
          />
        </Form.Item>
      </Form>
    </Card>
  );

  const renderFirstScreenTab = () => (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Card title="健康贴士轮播 + 空对话占位">
        <Form layout="vertical">
          <Divider plain>今日健康贴士轮播（紫色卡片，复用「轮播图」模块图片）</Divider>
          <Form.Item label="是否显示" extra="数据来源固定为后台「轮播图」模块">
            <Switch
              checked={draft.health_tips.visible}
              onChange={(c) => update((d) => { d.health_tips.visible = c; })}
            />
          </Form.Item>
          <FieldItem fieldKey="health_tips.interval_seconds" label="轮播间隔（秒，3~5）">
            <InputNumber
              min={3}
              max={5}
              value={draft.health_tips.interval_seconds}
              onChange={(v) => update((d) => { d.health_tips.interval_seconds = Number(v) || 4; })}
            />
          </FieldItem>
          <Form.Item label="是否显示底部小圆点指示器">
            <Switch
              checked={draft.health_tips.show_indicator}
              onChange={(c) => update((d) => { d.health_tips.show_indicator = c; })}
            />
          </Form.Item>

          <Divider plain>空对话占位（用户首次进入时显示）</Divider>
          <Form.Item label="占位图标 (Emoji)">
            <Input
              style={{ width: 120 }}
              value={draft.empty_placeholder.icon}
              maxLength={4}
              onChange={(e) => update((d) => { d.empty_placeholder.icon = e.target.value; })}
              placeholder="💬"
            />
          </Form.Item>
          <FieldItem fieldKey="empty_placeholder.main_title" label="主标题（≤20字）">
            <Input
              value={draft.empty_placeholder.main_title}
              maxLength={20}
              showCount
              onChange={(e) => update((d) => { d.empty_placeholder.main_title = e.target.value; })}
              placeholder="还没有对话记录"
            />
          </FieldItem>
        </Form>
      </Card>

      <Card title="推荐问列表（横向滚动胶囊，1~8 条）">
        <Paragraph type="secondary">
          用户进入 AI 对话首页时显示的推荐提问卡片。最多 20 条，前端最多展示 8 条（超出可滚动）。
        </Paragraph>
        {draft.recommended_questions.length === 0 && <Empty description="暂无推荐问" />}
        {draft.recommended_questions.map((q, idx) => (
          <Card
            key={q.id || idx}
            type="inner"
            size="small"
            style={{ marginBottom: 8 }}
            title={`#${idx + 1} ${q.title || '(未命名)'}`}
            extra={
              <Space>
                <Switch
                  checked={q.enabled}
                  onChange={(c) => updateRQ(idx, { enabled: c })}
                  checkedChildren="启用"
                  unCheckedChildren="禁用"
                />
                <Button size="small" icon={<ArrowUpOutlined />} disabled={idx === 0} onClick={() => moveRQ(idx, -1)} />
                <Button size="small" icon={<ArrowDownOutlined />} disabled={idx === draft.recommended_questions.length - 1} onClick={() => moveRQ(idx, 1)} />
                <Button size="small" danger icon={<DeleteOutlined />} onClick={() => removeRQ(idx)} />
              </Space>
            }
          >
            <Space direction="vertical" style={{ width: '100%' }} size={6}>
              <Space.Compact style={{ width: '100%' }}>
                <Input
                  style={{ width: 80 }}
                  value={q.icon}
                  onChange={(e) => updateRQ(idx, { icon: e.target.value })}
                  placeholder="📋"
                  maxLength={4}
                />
                <div data-field-key={`recommended_questions.${idx}.title`} style={{ flex: 1 }}>
                  <Input
                    style={{ width: '100%' }}
                    value={q.title}
                    onChange={(e) => updateRQ(idx, { title: e.target.value })}
                    placeholder="显示文案（≤8字）"
                    maxLength={8}
                    showCount
                    status={fieldErrors[`recommended_questions.${idx}.title`] ? 'error' : undefined}
                  />
                </div>
              </Space.Compact>
              <div data-field-key={`recommended_questions.${idx}.question`}>
                <Input.TextArea
                  rows={2}
                  value={q.question}
                  onChange={(e) => updateRQ(idx, { question: e.target.value })}
                  placeholder="实际发送内容（≤200字）"
                  maxLength={200}
                  showCount
                  status={fieldErrors[`recommended_questions.${idx}.question`] ? 'error' : undefined}
                />
              </div>
            </Space>
          </Card>
        ))}
        <Button type="dashed" icon={<PlusOutlined />} block onClick={addRQ} disabled={draft.recommended_questions.length >= 20}>
          新增推荐问 ({draft.recommended_questions.length}/20)
        </Button>
      </Card>
    </Space>
  );

  const renderFuncGridTab = () => (
    <Card title="功能宫格（每项 7 字段，1~6 项）">
      <Paragraph type="secondary">
        每项含主文案、副说明、跳转链接、图标、渐变色（起始+结束）、角标、是否启用 7 字段。最少 1 项、最多 6 项。
      </Paragraph>
      {fieldErrors['func_grid.items'] && (
        <Alert type="error" showIcon style={{ marginBottom: 12 }} message={fieldErrors['func_grid.items']} />
      )}
      <Form layout="inline" style={{ marginBottom: 12 }}>
        <Form.Item label="布局列数">
          <Radio.Group
            value={draft.func_grid.columns}
            onChange={(e) => update((d) => { d.func_grid.columns = e.target.value; })}
          >
            <Radio value={2}>2 列</Radio>
            <Radio value={3}>3 列</Radio>
            <Radio value={4}>4 列</Radio>
          </Radio.Group>
        </Form.Item>
      </Form>
      {draft.func_grid.items.length === 0 && <Empty description="至少 1 项" />}
      {draft.func_grid.items.map((it, idx) => (
        <Card
          key={it.id || idx}
          type="inner"
          size="small"
          style={{ marginBottom: 8 }}
          title={`#${idx + 1} ${it.main_text || '(未命名)'}`}
          extra={
            <Space>
              <Switch
                checked={it.enabled}
                onChange={(c) => update((d) => { d.func_grid.items[idx].enabled = c; })}
                checkedChildren="启用"
                unCheckedChildren="禁用"
              />
              <Button size="small" icon={<ArrowUpOutlined />} disabled={idx === 0}
                onClick={() => update((d) => {
                  const list = d.func_grid.items;
                  [list[idx], list[idx - 1]] = [list[idx - 1], list[idx]];
                  list.forEach((x, i) => (x.sort = i + 1));
                })}
              />
              <Button size="small" icon={<ArrowDownOutlined />} disabled={idx === draft.func_grid.items.length - 1}
                onClick={() => update((d) => {
                  const list = d.func_grid.items;
                  [list[idx], list[idx + 1]] = [list[idx + 1], list[idx]];
                  list.forEach((x, i) => (x.sort = i + 1));
                })}
              />
              <Button size="small" danger icon={<DeleteOutlined />} disabled={draft.func_grid.items.length <= 1}
                onClick={() => update((d) => { d.func_grid.items.splice(idx, 1); })}
              />
            </Space>
          }
        >
          <Row gutter={12}>
            <Col span={8}>
              <FieldItem fieldKey={`func_grid.items.${idx}.main_text`} label="主文案（≤8字）">
                <Input
                  value={it.main_text}
                  maxLength={8}
                  showCount
                  onChange={(e) => update((d) => { d.func_grid.items[idx].main_text = e.target.value; })}
                  placeholder="如：AI诊室"
                />
              </FieldItem>
            </Col>
            <Col span={8}>
              <FieldItem fieldKey={`func_grid.items.${idx}.sub_text`} label="副说明（≤12字）">
                <Input
                  value={it.sub_text}
                  maxLength={12}
                  showCount
                  onChange={(e) => update((d) => { d.func_grid.items[idx].sub_text = e.target.value; })}
                  placeholder="如：智能问诊"
                />
              </FieldItem>
            </Col>
            <Col span={8}>
              <Form.Item label="跳转链接（/ 或 http(s)://）">
                <Input
                  value={it.target_path}
                  onChange={(e) => update((d) => { d.func_grid.items[idx].target_path = e.target.value; })}
                  placeholder="/ai-doctor"
                />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item label="图标（Emoji）">
                <Input
                  value={it.icon}
                  maxLength={4}
                  onChange={(e) => update((d) => { d.func_grid.items[idx].icon = e.target.value; })}
                  placeholder="🩺"
                />
              </Form.Item>
            </Col>
            <Col span={6}>
              <FieldItem fieldKey={`func_grid.items.${idx}.gradient_start`} label="渐变起始色">
                <Input
                  value={it.gradient_start}
                  onChange={(e) => update((d) => { d.func_grid.items[idx].gradient_start = e.target.value; })}
                  placeholder="#5B6CFF"
                  addonAfter={
                    <input
                      type="color"
                      value={it.gradient_start}
                      onChange={(e) => update((d) => { d.func_grid.items[idx].gradient_start = e.target.value; })}
                      style={{ width: 24, height: 24, border: 'none', padding: 0, background: 'transparent' }}
                    />
                  }
                />
              </FieldItem>
            </Col>
            <Col span={6}>
              <FieldItem fieldKey={`func_grid.items.${idx}.gradient_end`} label="渐变结束色">
                <Input
                  value={it.gradient_end}
                  onChange={(e) => update((d) => { d.func_grid.items[idx].gradient_end = e.target.value; })}
                  placeholder="#8B9AFF"
                  addonAfter={
                    <input
                      type="color"
                      value={it.gradient_end}
                      onChange={(e) => update((d) => { d.func_grid.items[idx].gradient_end = e.target.value; })}
                      style={{ width: 24, height: 24, border: 'none', padding: 0, background: 'transparent' }}
                    />
                  }
                />
              </FieldItem>
            </Col>
            <Col span={6}>
              <Form.Item label="角标（≤4字，可空）">
                <Input
                  value={it.badge || ''}
                  maxLength={4}
                  onChange={(e) => update((d) => { d.func_grid.items[idx].badge = e.target.value; })}
                  placeholder="如：NEW / HOT"
                />
              </Form.Item>
            </Col>
          </Row>
          <div
            style={{
              marginTop: 4,
              padding: 12,
              borderRadius: 12,
              background: `linear-gradient(135deg, ${it.gradient_start} 0%, ${it.gradient_end} 100%)`,
              color: '#fff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <span style={{ fontSize: 28 }}>{it.icon}</span>
            <div>
              <div style={{ fontWeight: 600 }}>{it.main_text || '主文案'}</div>
              <div style={{ fontSize: 12, opacity: 0.9 }}>{it.sub_text || '副说明'}</div>
            </div>
            {it.badge && (
              <span style={{ background: '#FF4D4F', borderRadius: 8, padding: '2px 6px', fontSize: 10 }}>{it.badge}</span>
            )}
          </div>
        </Card>
      ))}
      <Button
        type="dashed"
        icon={<PlusOutlined />}
        block
        disabled={draft.func_grid.items.length >= 6}
        onClick={() => update((d) => {
          d.func_grid.items.push({
            main_text: '',
            sub_text: '',
            target_path: '/',
            icon: '✨',
            gradient_start: '#5B6CFF',
            gradient_end: '#8B9AFF',
            badge: '',
            enabled: true,
            sort: d.func_grid.items.length + 1,
          });
        })}
      >
        新增宫格项 ({draft.func_grid.items.length}/6)
      </Button>
    </Card>
  );

  const renderInputTab = () => (
    <Card title="输入栏配置（含家庭成员咨询胶囊）">
      <Form layout="vertical">
        <Form.Item label="占位符文案">
          <Input
            value={draft.input.placeholder}
            onChange={(e) => update((d) => { d.input.placeholder = e.target.value; })}
            maxLength={40}
          />
        </Form.Item>
        <Form.Item label="启用 🎤 语音输入按钮">
          <Switch
            checked={draft.input.enable_voice}
            onChange={(c) => update((d) => { d.input.enable_voice = c; })}
          />
        </Form.Item>
        <Form.Item label="启用 AI 回复 TTS 播报按钮">
          <Switch
            checked={draft.input.enable_tts}
            onChange={(c) => update((d) => { d.input.enable_tts = c; })}
          />
        </Form.Item>
        <Form.Item label="默认 TTS 提供方">
          <Select
            style={{ width: 180 }}
            value={draft.input.tts_provider}
            onChange={(v) => update((d) => { d.input.tts_provider = v; })}
            options={[
              { value: 'auto', label: '自动（云端优先）' },
              { value: 'cloud', label: '云端' },
              { value: 'browser', label: '浏览器' },
            ]}
          />
        </Form.Item>

        <Divider plain>家庭成员咨询胶囊（输入框下方第二层）</Divider>
        <Form.Item label="是否显示家庭成员咨询胶囊">
          <Switch
            checked={draft.input.family_consult.enabled}
            onChange={(c) => update((d) => { d.input.family_consult.enabled = c; })}
          />
        </Form.Item>
        <FieldItem fieldKey="input.family_consult.template" label="胶囊默认文案模板（必含 {name}，≤20字）" tooltip="必须包含 {name} 占位符">
          <Input
            value={draft.input.family_consult.template}
            onChange={(e) => update((d) => { d.input.family_consult.template = e.target.value; })}
            maxLength={20}
            showCount
            placeholder="为({name})咨询"
          />
        </FieldItem>
        <Form.Item label="是否显示「查看档案」按钮">
          <Switch
            checked={draft.input.family_consult.show_archive_link}
            onChange={(c) => update((d) => { d.input.family_consult.show_archive_link = c; })}
          />
        </Form.Item>
        <Form.Item label="查看档案跳转链接">
          <Input
            value={draft.input.family_consult.archive_path}
            onChange={(e) => update((d) => { d.input.family_consult.archive_path = e.target.value; })}
            placeholder="/health-records"
          />
        </Form.Item>
      </Form>
    </Card>
  );

  const renderSessionTab = () => (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Card title="会话策略（7 个全局字段）">
        <Form layout="vertical">
          <Row gutter={16}>
            <Col span={8}>
              <FieldItem fieldKey="session.strategy.max_answer_chars" label="单次回答最大字数（100~5000）">
                <InputNumber
                  min={100}
                  max={5000}
                  value={draft.session.strategy.max_answer_chars}
                  onChange={(v) => update((d) => { d.session.strategy.max_answer_chars = Number(v) || 1000; })}
                  style={{ width: '100%' }}
                />
              </FieldItem>
            </Col>
            <Col span={8}>
              <FieldItem fieldKey="session.strategy.daily_free_quota" label="单日免费提问次数上限（1~999）">
                <InputNumber
                  min={1}
                  max={999}
                  value={draft.session.strategy.daily_free_quota}
                  onChange={(v) => update((d) => { d.session.strategy.daily_free_quota = Number(v) || 50; })}
                  style={{ width: '100%' }}
                />
              </FieldItem>
            </Col>
            <Col span={8}>
              <Form.Item label="上下文记忆轮数">
                <Select
                  value={draft.session.strategy.context_memory_rounds}
                  onChange={(v) => update((d) => { d.session.strategy.context_memory_rounds = v; })}
                  options={[
                    { value: 3, label: '3 轮' },
                    { value: 5, label: '5 轮' },
                    { value: 10, label: '10 轮' },
                    { value: 20, label: '20 轮' },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="默认回答风格">
            <Radio.Group
              value={draft.session.strategy.answer_style}
              onChange={(e) => update((d) => { d.session.strategy.answer_style = e.target.value; })}
            >
              <Radio value="professional">专业医学术语</Radio>
              <Radio value="easy">通俗易懂</Radio>
              <Radio value="friendly">温馨亲切</Radio>
            </Radio.Group>
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="启用「AI 思考中...」加载动画">
                <Switch
                  checked={draft.session.strategy.show_loading}
                  onChange={(c) => update((d) => { d.session.strategy.show_loading = c; })}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="敏感词过滤开关">
                <Switch
                  checked={draft.session.strategy.sensitive_filter}
                  onChange={(c) => update((d) => { d.session.strategy.sensitive_filter = c; })}
                />
              </Form.Item>
            </Col>
          </Row>
          <FieldItem fieldKey="session.strategy.disclaimer" label="免责声明文案（≤100字，每次回答末尾自动追加）">
            <Input.TextArea
              rows={2}
              value={draft.session.strategy.disclaimer}
              maxLength={100}
              showCount
              onChange={(e) => update((d) => { d.session.strategy.disclaimer = e.target.value; })}
              placeholder="以上内容仅供参考，不能替代医生诊疗"
            />
          </FieldItem>
        </Form>
      </Card>

      <Card title="空闲超时与空会话引导">
        <Form layout="vertical">
          <Form.Item label="空闲超时分钟数" extra="与现有 chat-idle-timeout 接口共用同一存储">
            <InputNumber
              min={1}
              max={1440}
              value={draft.session.idle_timeout_minutes}
              onChange={(v) => update((d) => { d.session.idle_timeout_minutes = Number(v) || 30; })}
            />
          </Form.Item>
          <Form.Item label="启用空闲自动新会话">
            <Switch
              checked={draft.session.auto_new_session}
              onChange={(c) => update((d) => { d.session.auto_new_session = c; })}
            />
          </Form.Item>
          <Divider plain>空会话引导</Divider>
          <Form.Item label="进入空会话时自动播放 AI 欢迎语">
            <Switch
              checked={draft.session.empty_session_welcome.enabled}
              onChange={(c) => update((d) => { d.session.empty_session_welcome.enabled = c; })}
            />
          </Form.Item>
          <Form.Item label="欢迎语内容（多条随机抽 1）">
            <StringListEditor
              value={draft.session.empty_session_welcome.messages}
              onChange={(v) => update((d) => { d.session.empty_session_welcome.messages = v; })}
              placeholder="例如：你好，我是你的 AI 健康助手"
              max={20}
            />
          </Form.Item>
        </Form>
      </Card>
    </Space>
  );

  const renderGlobalTab = () => (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Card title="全局开关（9 个模块级总开关）">
        <Paragraph type="secondary">
          子项级开关由各项内部的「是否启用」字段承担。本卡片只放<strong>模块级</strong>开关，与对应字段 Tab 的「是否启用」联动取并集——只要其中一处关闭，模块即不显示。
        </Paragraph>
        <Row gutter={[16, 16]}>
          {[
            { key: 'welcome_visible', label: '1. 欢迎区 - 整块显隐' },
            { key: 'health_tips_visible', label: '2. 今日健康贴士 - 整块显隐' },
            { key: 'func_grid_visible', label: '3. 功能宫格 - 整块显隐' },
            { key: 'recommended_visible', label: '4. 推荐问 - 整块显隐' },
            { key: 'empty_placeholder_visible', label: '5. 空对话占位 - 整块显隐' },
            { key: 'family_pill_visible', label: '6. 输入栏 - 家庭成员咨询胶囊' },
            { key: 'archive_link_visible', label: '7. 输入栏 - 查看档案按钮' },
            { key: 'voice_input_visible', label: '8. 输入栏 - 语音输入图标' },
            { key: 'floating_button_visible', label: '9. 打卡悬浮按钮 - 整块显隐' },
          ].map((item) => (
            <Col span={8} key={item.key}>
              <Form.Item label={item.label} style={{ marginBottom: 0 }}>
                <Switch
                  checked={(draft.global_switches as any)[item.key]}
                  onChange={(c) => update((d) => { (d.global_switches as any)[item.key] = c; })}
                />
              </Form.Item>
            </Col>
          ))}
        </Row>
      </Card>

      <Card title="浮动健康打卡按钮（4 字段精简版）">
        <Form layout="vertical">
          <Form.Item label="是否显示">
            <Switch
              checked={draft.floating_button.enabled}
              onChange={(c) => update((d) => { d.floating_button.enabled = c; })}
            />
          </Form.Item>
          <Form.Item label="图标 (emoji)">
            <Input
              style={{ width: 120 }}
              value={draft.floating_button.icon}
              onChange={(e) => update((d) => { d.floating_button.icon = e.target.value; })}
              maxLength={4}
            />
          </Form.Item>
          <Form.Item label="按钮文字">
            <Input
              style={{ width: 240 }}
              value={draft.floating_button.label || ''}
              onChange={(e) => update((d) => { d.floating_button.label = e.target.value; })}
              maxLength={10}
              placeholder="健康打卡"
            />
          </Form.Item>
          <Form.Item label="是否显示文字">
            <Switch
              checked={draft.floating_button.show_label}
              onChange={(c) => update((d) => { d.floating_button.show_label = c; })}
            />
          </Form.Item>
          <Form.Item label="跳转路径（项目内）" extra="必须以 / 开头，禁止外链">
            <Input
              style={{ width: 300 }}
              value={draft.floating_button.target_path}
              onChange={(e) => update((d) => { d.floating_button.target_path = e.target.value; })}
              placeholder="/health-check-in"
            />
          </Form.Item>
          <Form.Item label="显示位置">
            <Radio.Group
              value={draft.floating_button.position}
              onChange={(e) => update((d) => { d.floating_button.position = e.target.value; })}
            >
              <Radio value="right_bottom">右下</Radio>
              <Radio value="left_bottom">左下</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Card>

      <Card title="顶栏与品牌（兼容旧 H5；设计图无顶栏，本卡片末位渲染）">
        <Form layout="vertical">
          <Form.Item label="是否显示顶栏（v1.0 设计图为关闭）">
            <Switch
              checked={draft.topbar.visible}
              onChange={(c) => update((d) => { d.topbar.visible = c; })}
            />
          </Form.Item>
          <Form.Item label="标题文案">
            <Input
              value={draft.topbar.title}
              onChange={(e) => update((d) => { d.topbar.title = e.target.value; })}
              maxLength={30}
              placeholder="AI 健康助手"
            />
          </Form.Item>
          <Form.Item label="Logo">
            <AvatarEditor
              value={draft.topbar.logo}
              onChange={(v) => update((d) => { d.topbar.logo = v; })}
              uploadAction={upload}
            />
          </Form.Item>
          <Form.Item label="显示左侧 ☰ 侧边栏入口">
            <Switch
              checked={draft.topbar.show_sidebar}
              onChange={(c) => update((d) => { d.topbar.show_sidebar = c; })}
            />
          </Form.Item>
          <Form.Item label="显示右侧 ··· 更多菜单">
            <Switch
              checked={draft.topbar.show_more_menu}
              onChange={(c) => update((d) => { d.topbar.show_more_menu = c; })}
            />
          </Form.Item>
          <Form.Item label="显示分享按钮">
            <Switch
              checked={draft.topbar.show_share}
              onChange={(c) => update((d) => { d.topbar.show_share = c; })}
            />
          </Form.Item>
        </Form>
      </Card>

      {/* PRD-414 v1.1：AI 对话页（chat 页）配置 */}
      <Card title="AI 对话页（chat）配置 — PRD-414 v1.1">
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="此区域配置 AI 对话页的关键体验：AI 头像（与品牌 Logo 解耦，单独维护）、署名、档案行文案、是否允许拖动健康打卡、是否显示「↓回到最新」按钮、顶栏是否吸顶、历史会话保留时长。"
        />
        <Form layout="vertical">
          <Form.Item
            label="AI 对话头像（推荐 128×128，PNG/JPG/WEBP，≤500KB；与系统 Logo 完全独立维护）"
            data-field-key="ai_chat.avatar"
          >
            <AvatarEditor
              value={draft.ai_chat.avatar}
              onChange={(v) => update((d) => { d.ai_chat.avatar = v; })}
              uploadAction={upload}
            />
          </Form.Item>
          <Form.Item
            label="AI 署名（默认「小康」，≤10 字）"
            help={fieldErrors['ai_chat.signature']}
            validateStatus={fieldErrors['ai_chat.signature'] ? 'error' : undefined}
            data-field-key="ai_chat.signature"
          >
            <Input
              value={draft.ai_chat.signature}
              onChange={(e) => update((d) => { d.ai_chat.signature = e.target.value; })}
              maxLength={10}
              showCount
              placeholder="小康"
            />
          </Form.Item>
          <Form.Item label="档案行总开关（每条 AI 回答上方是否显示「本次回答结合 XX 的档案 ▽」）">
            <Switch
              checked={draft.ai_chat.profile_row_enabled}
              onChange={(c) => update((d) => { d.ai_chat.profile_row_enabled = c; })}
            />
          </Form.Item>
          <Form.Item
            label="档案行文案模板（必须包含 {name} 占位符）"
            help={fieldErrors['ai_chat.profile_row_template']}
            validateStatus={fieldErrors['ai_chat.profile_row_template'] ? 'error' : undefined}
            data-field-key="ai_chat.profile_row_template"
          >
            <Input
              value={draft.ai_chat.profile_row_template}
              onChange={(e) => update((d) => { d.ai_chat.profile_row_template = e.target.value; })}
              maxLength={30}
              showCount
              placeholder="本次回答结合 {name} 的档案"
            />
          </Form.Item>
          <Form.Item label="健康打卡可拖动（仅垂直方向，长按 200ms 进入拖动态）">
            <Switch
              checked={draft.ai_chat.punchcard_draggable}
              onChange={(c) => update((d) => { d.ai_chat.punchcard_draggable = c; })}
            />
          </Form.Item>
          <Form.Item label="显示「↓ 回到最新消息」按钮（用户上滑超过 100px 时浮出）">
            <Switch
              checked={draft.ai_chat.scroll_to_bottom_button}
              onChange={(c) => update((d) => { d.ai_chat.scroll_to_bottom_button = c; })}
            />
          </Form.Item>
          <Form.Item label="顶栏吸顶（始终固定在屏幕顶端）">
            <Switch
              checked={draft.ai_chat.sticky_topbar}
              onChange={(c) => update((d) => { d.ai_chat.sticky_topbar = c; })}
            />
          </Form.Item>
          <Form.Item
            label="历史会话保留天数（0 = 永久保留；最大 3650 天）"
            help={fieldErrors['ai_chat.history_retention_days']}
            validateStatus={fieldErrors['ai_chat.history_retention_days'] ? 'error' : undefined}
            data-field-key="ai_chat.history_retention_days"
          >
            <InputNumber
              min={0}
              max={3650}
              value={draft.ai_chat.history_retention_days}
              onChange={(v) => update((d) => { d.ai_chat.history_retention_days = (v ?? 0) as number; })}
              style={{ width: 200 }}
            />
            <Text type="secondary" style={{ marginLeft: 8 }}>
              当前：{draft.ai_chat.history_retention_days === 0 ? '永久保留' : `${draft.ai_chat.history_retention_days} 天`}
            </Text>
          </Form.Item>
        </Form>
      </Card>
    </Space>
  );

  // ──────────────── Tab 内容映射 ────────────────

  const tabRenderers: Record<TabKey, () => React.ReactNode> = {
    welcome: renderWelcomeTab,
    first_screen: renderFirstScreenTab,
    func_grid: renderFuncGridTab,
    input: renderInputTab,
    session: renderSessionTab,
    global: renderGlobalTab,
  };

  // ──────────────── 渲染主体 ────────────────

  return (
    <Spin spinning={loading}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          AI 对话模式首页配置
        </Title>
        <Space>
          <Button
            icon={<HistoryOutlined />}
            onClick={() => router.push('/home-settings/ai-home-config/logs')}
          >
            操作日志
          </Button>
          <Button icon={<ReloadOutlined />} onClick={fetchConfig}>
            刷新
          </Button>
        </Space>
      </div>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="每个 Tab 仅显示该模块的卡片，避免长页面滚动。Tab 标题旁红点 ● 表示有未保存改动；切 Tab 会弹出确认框，避免误丢草稿。"
      />

      {/* 真 Tab 切换：仅当前 Tab 内容渲染 */}
      <Tabs
        activeKey={activeTab}
        onTabClick={(key) => trySwitchTab(key as TabKey)}
        destroyInactiveTabPane
        style={{ marginBottom: 16 }}
        items={TAB_META.map((t) => ({
          key: t.key,
          label: dirtyMap[t.key] ? (
            <Badge dot color="#FF4D4F" offset={[6, -2]}>
              <span>{t.label}</span>
            </Badge>
          ) : (
            <span>{t.label}</span>
          ),
          children: <div style={{ paddingBottom: 80 }}>{tabRenderers[t.key]()}</div>,
        }))}
      />

      {/* 吸底操作栏（每个 Tab 共享，按当前 Tab 上下文操作） */}
      <div
        style={{
          position: 'sticky',
          bottom: 0,
          left: 0,
          right: 0,
          background: '#fff',
          borderTop: '1px solid #f0f0f0',
          padding: '12px 16px',
          marginTop: 16,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          zIndex: 10,
          boxShadow: '0 -2px 8px rgba(0,0,0,0.04)',
        }}
      >
        <Text type="secondary">
          当前 Tab：<strong>{TAB_META.find((t) => t.key === activeTab)?.label}</strong>
          {currentTabDirty && <span style={{ color: '#FF4D4F', marginLeft: 8 }}>● 有未保存改动</span>}
        </Text>
        <Space>
          <Button
            icon={<ReloadOutlined />}
            disabled={!currentTabDirty || saving}
            onClick={() => resetTab(activeTab)}
          >
            重置本 Tab
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            disabled={!currentTabDirty}
            loading={saving}
            onClick={() => saveTab(activeTab)}
          >
            保存本 Tab
          </Button>
        </Space>
      </div>

      {/* 切 Tab 三选确认框（受控） */}
      <Modal
        open={pendingTargetTab !== null}
        title="未保存的修改"
        onCancel={handleCancelSwitch}
        maskClosable={false}
        footer={
          <Space>
            <Button onClick={handleCancelSwitch}>取消</Button>
            <Button danger onClick={handleDiscardAndSwitch}>
              放弃修改并切换
            </Button>
            <Button type="primary" loading={saving} onClick={handleConfirmSaveAndSwitch}>
              保存并切换
            </Button>
          </Space>
        }
      >
        <p>
          当前 Tab「{TAB_META.find((t) => t.key === activeTab)?.label}」中有未保存的修改，您希望如何处理？
        </p>
      </Modal>
    </Spin>
  );
}
