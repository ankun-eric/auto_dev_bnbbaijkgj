'use client';

import React, { useEffect, useState, useCallback } from 'react';
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
  Tag,
  Upload,
  Radio,
  InputNumber,
  Modal,
  Table,
  Empty,
  Divider,
  Alert,
  Tabs,
  Row,
  Col,
  ColorPicker,
  Tooltip,
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

// ─── 字符串数组编辑器 ─────────────────────────────
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

// ─── 头像/Logo 编辑器 ─────────────────────────────
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
              style={{
                width: 64,
                height: 64,
                borderRadius: 8,
                objectFit: 'cover',
                border: '1px solid #eee',
              }}
            />
          ) : (
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: 8,
                background: '#f5f5f5',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#aaa',
              }}
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

// ─── 主页面 ─────────────────────────────
export default function AIHomeConfigPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [cfg, setCfg] = useState<Cfg>(DEFAULT_CFG);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<{ config: Cfg }>('/api/admin/ai-home-config');
      const merged = { ...DEFAULT_CFG, ...(res.config || {}) } as Cfg;
      setCfg(merged);
    } catch {
      message.error('加载配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

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

  const saveModule = async (mod: string, data: any) => {
    setSaving(true);
    try {
      const res = await patch<{ config: Cfg }>(
        `/api/admin/ai-home-config/${mod}`,
        { data }
      );
      setCfg({ ...DEFAULT_CFG, ...(res.config || {}) } as Cfg);
      message.success('已保存');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const saveAll = async () => {
    setSaving(true);
    try {
      const res = await put<{ config: Cfg }>('/api/admin/ai-home-config', cfg);
      setCfg({ ...DEFAULT_CFG, ...(res.config || {}) } as Cfg);
      message.success('全部保存成功');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const resetModule = (mod: keyof Cfg) => {
    Modal.confirm({
      title: '重置为默认值？',
      onOk: () => setCfg({ ...cfg, [mod]: (DEFAULT_CFG as any)[mod] } as Cfg),
    });
  };

  // 推荐问操作
  const updateRQ = (idx: number, patchObj: Partial<RecommendedQ>) => {
    const list = [...cfg.recommended_questions];
    list[idx] = { ...list[idx], ...patchObj };
    setCfg({ ...cfg, recommended_questions: list });
  };
  const addRQ = () => {
    if (cfg.recommended_questions.length >= 20) {
      message.warning('最多 20 条');
      return;
    }
    setCfg({
      ...cfg,
      recommended_questions: [
        ...cfg.recommended_questions,
        {
          id: '',
          icon: '💡',
          title: '新推荐问',
          question: '',
          enabled: true,
          sort: (cfg.recommended_questions[cfg.recommended_questions.length - 1]?.sort ?? 0) + 1,
        },
      ],
    });
  };
  const removeRQ = (idx: number) => {
    const list = [...cfg.recommended_questions];
    list.splice(idx, 1);
    setCfg({ ...cfg, recommended_questions: list });
  };
  const moveRQ = (idx: number, delta: number) => {
    const list = [...cfg.recommended_questions];
    const target = idx + delta;
    if (target < 0 || target >= list.length) return;
    [list[idx], list[target]] = [list[target], list[idx]];
    list.forEach((it, i) => {
      it.sort = i + 1;
    });
    setCfg({ ...cfg, recommended_questions: list });
  };

  return (
    <Spin spinning={loading || saving}>
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
        message="点击每张卡片右上角『保存本节』可单独保存该模块；底部『全部保存』一次性保存全部配置。配置保存后立即对所有用户端生效。"
      />

      {/* PRD-405 v1.0：6 Tab 导航锚点（点击滚动到对应卡片） */}
      <Card style={{ marginBottom: 16, position: 'sticky', top: 0, zIndex: 6 }} bodyStyle={{ padding: '8px 16px' }}>
        <Tabs
          size="small"
          defaultActiveKey="welcome"
          onTabClick={(key) => {
            const el = document.getElementById(`anchor-${key}`);
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }}
          items={[
            { key: 'welcome', label: '1. 欢迎区' },
            { key: 'first-screen', label: '2. 首屏内容' },
            { key: 'func-grid', label: '3. 功能宫格' },
            { key: 'input', label: '4. 输入栏' },
            { key: 'session-strategy', label: '5. 会话策略' },
            { key: 'global-switches', label: '6. 全局开关' },
          ]}
        />
      </Card>

      {/* 1. 欢迎区 */}
      <Card
        id="anchor-welcome"
        title="Tab 1 · 欢迎区配置"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button onClick={() => resetModule('welcome')}>重置默认</Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={() => saveModule('welcome', cfg.welcome)}
            >
              保存本节
            </Button>
          </Space>
        }
      >
        <Form layout="vertical">
          <Tooltip title="支持 {昵称} 占位符，自动替换为用户昵称。如：早上好，{昵称}！">
            <Form.Item label="主标题（首页大字，≤30字）">
              <Input
                value={cfg.welcome.main_title}
                maxLength={30}
                showCount
                onChange={(e) =>
                  setCfg({ ...cfg, welcome: { ...cfg.welcome, main_title: e.target.value } })
                }
                placeholder="早上好，{昵称}！"
              />
            </Form.Item>
          </Tooltip>
          <Form.Item label="副标题（≤50字）">
            <Input
              value={cfg.welcome.sub_title}
              maxLength={50}
              showCount
              onChange={(e) =>
                setCfg({ ...cfg, welcome: { ...cfg.welcome, sub_title: e.target.value } })
              }
              placeholder="我是您的AI健康顾问小康"
            />
          </Form.Item>
          <Form.Item label="头像">
            <AvatarEditor
              value={cfg.welcome.avatar}
              onChange={(v) =>
                setCfg({ ...cfg, welcome: { ...cfg.welcome, avatar: v } })
              }
              uploadAction={upload}
            />
          </Form.Item>
          <Divider plain>多条问候语随机抽 1（兼容旧版本）</Divider>
          <Form.Item label="早上问候语 (05:00-12:00)">
            <StringListEditor
              value={cfg.welcome.greetings.morning}
              onChange={(v) =>
                setCfg({
                  ...cfg,
                  welcome: {
                    ...cfg.welcome,
                    greetings: { ...cfg.welcome.greetings, morning: v },
                  },
                })
              }
              placeholder="例如：早上好"
            />
          </Form.Item>
          <Form.Item label="下午问候语 (12:00-18:00)">
            <StringListEditor
              value={cfg.welcome.greetings.afternoon}
              onChange={(v) =>
                setCfg({
                  ...cfg,
                  welcome: {
                    ...cfg.welcome,
                    greetings: { ...cfg.welcome.greetings, afternoon: v },
                  },
                })
              }
              placeholder="例如：午安"
            />
          </Form.Item>
          <Form.Item label="晚上问候语 (18:00-次日 05:00)">
            <StringListEditor
              value={cfg.welcome.greetings.evening}
              onChange={(v) =>
                setCfg({
                  ...cfg,
                  welcome: {
                    ...cfg.welcome,
                    greetings: { ...cfg.welcome.greetings, evening: v },
                  },
                })
              }
              placeholder="例如：晚上好"
            />
          </Form.Item>
          <Form.Item label="副标题（多条随机抽 1）">
            <StringListEditor
              value={cfg.welcome.subtitles}
              onChange={(v) =>
                setCfg({ ...cfg, welcome: { ...cfg.welcome, subtitles: v } })
              }
              placeholder="例如：有什么健康问题想问我?"
            />
          </Form.Item>
          <Form.Item label="是否在问候语后拼接用户昵称">
            <Switch
              checked={cfg.welcome.show_nickname}
              onChange={(c) =>
                setCfg({ ...cfg, welcome: { ...cfg.welcome, show_nickname: c } })
              }
            />
          </Form.Item>
        </Form>
      </Card>

      {/* 2. 顶栏与品牌（设计图无顶栏，本卡片保留兼容旧 H5） */}
      <Card
        id="anchor-topbar"
        title="补充 · 顶栏与品牌配置（设计图无顶栏，仅兼容旧版 H5）"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button onClick={() => resetModule('topbar')}>重置默认</Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={() => saveModule('topbar', cfg.topbar)}
            >
              保存本节
            </Button>
          </Space>
        }
      >
        <Form layout="vertical">
          <Form.Item label="是否显示顶栏（v1.0 设计图为关闭）">
            <Switch
              checked={cfg.topbar.visible}
              onChange={(c) =>
                setCfg({ ...cfg, topbar: { ...cfg.topbar, visible: c } })
              }
            />
          </Form.Item>
          <Form.Item label="标题文案">
            <Input
              value={cfg.topbar.title}
              onChange={(e) =>
                setCfg({ ...cfg, topbar: { ...cfg.topbar, title: e.target.value } })
              }
              maxLength={30}
              placeholder="AI 健康助手"
            />
          </Form.Item>
          <Form.Item label="Logo">
            <AvatarEditor
              value={cfg.topbar.logo}
              onChange={(v) =>
                setCfg({ ...cfg, topbar: { ...cfg.topbar, logo: v } })
              }
              uploadAction={upload}
            />
          </Form.Item>
          <Form.Item label="显示左侧 ☰ 侧边栏入口">
            <Switch
              checked={cfg.topbar.show_sidebar}
              onChange={(c) =>
                setCfg({ ...cfg, topbar: { ...cfg.topbar, show_sidebar: c } })
              }
            />
          </Form.Item>
          <Form.Item label="显示右侧 ··· 更多菜单">
            <Switch
              checked={cfg.topbar.show_more_menu}
              onChange={(c) =>
                setCfg({ ...cfg, topbar: { ...cfg.topbar, show_more_menu: c } })
              }
            />
          </Form.Item>
          <Form.Item label="显示分享按钮">
            <Switch
              checked={cfg.topbar.show_share}
              onChange={(c) =>
                setCfg({ ...cfg, topbar: { ...cfg.topbar, show_share: c } })
              }
            />
          </Form.Item>
        </Form>
      </Card>

      {/* Tab 2 · 首屏内容：健康贴士轮播 + 推荐问 + 空对话占位 */}
      <Card
        id="anchor-first-screen"
        title="Tab 2 · 首屏内容（健康贴士轮播 + 空对话占位）"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={async () => {
                await saveModule('health_tips', cfg.health_tips);
                await saveModule('empty_placeholder', cfg.empty_placeholder);
              }}
            >
              保存本节
            </Button>
          </Space>
        }
      >
        <Form layout="vertical">
          <Divider plain>今日健康贴士轮播（紫色卡片，复用「轮播图」模块图片）</Divider>
          <Form.Item label="是否显示" extra="数据来源固定为后台「轮播图」模块">
            <Switch
              checked={cfg.health_tips.visible}
              onChange={(c) => setCfg({ ...cfg, health_tips: { ...cfg.health_tips, visible: c } })}
            />
          </Form.Item>
          <Form.Item label="轮播间隔（秒，3~5）">
            <InputNumber
              min={3}
              max={5}
              value={cfg.health_tips.interval_seconds}
              onChange={(v) =>
                setCfg({ ...cfg, health_tips: { ...cfg.health_tips, interval_seconds: Number(v) || 4 } })
              }
            />
          </Form.Item>
          <Form.Item label="是否显示底部小圆点指示器">
            <Switch
              checked={cfg.health_tips.show_indicator}
              onChange={(c) => setCfg({ ...cfg, health_tips: { ...cfg.health_tips, show_indicator: c } })}
            />
          </Form.Item>

          <Divider plain>空对话占位（用户首次进入时显示）</Divider>
          <Form.Item label="占位图标 (Emoji)">
            <Input
              style={{ width: 120 }}
              value={cfg.empty_placeholder.icon}
              maxLength={4}
              onChange={(e) => setCfg({ ...cfg, empty_placeholder: { ...cfg.empty_placeholder, icon: e.target.value } })}
              placeholder="💬"
            />
          </Form.Item>
          <Form.Item label="主标题（≤20字）">
            <Input
              value={cfg.empty_placeholder.main_title}
              maxLength={20}
              showCount
              onChange={(e) => setCfg({ ...cfg, empty_placeholder: { ...cfg.empty_placeholder, main_title: e.target.value } })}
              placeholder="还没有对话记录"
            />
          </Form.Item>
        </Form>
      </Card>

      {/* 3. 推荐问 */}
      <Card
        id="anchor-recommended"
        title='Tab 2 · 推荐问列表（横向滚动胶囊，1~8 条）'
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button onClick={() => resetModule('recommended_questions')}>
              清空
            </Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={() =>
                saveModule('recommended_questions', cfg.recommended_questions)
              }
            >
              保存本节
            </Button>
          </Space>
        }
      >
        <Paragraph type="secondary">
          用户进入 AI 对话首页时显示的推荐提问卡片。最多 20 条，前端最多展示 8 条（超出可滚动）。
        </Paragraph>
        {cfg.recommended_questions.length === 0 && <Empty description="暂无推荐问" />}
        {cfg.recommended_questions.map((q, idx) => (
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
                <Button
                  size="small"
                  icon={<ArrowUpOutlined />}
                  disabled={idx === 0}
                  onClick={() => moveRQ(idx, -1)}
                />
                <Button
                  size="small"
                  icon={<ArrowDownOutlined />}
                  disabled={idx === cfg.recommended_questions.length - 1}
                  onClick={() => moveRQ(idx, 1)}
                />
                <Button
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => removeRQ(idx)}
                />
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
                <Input
                  style={{ flex: 1 }}
                  value={q.title}
                  onChange={(e) => updateRQ(idx, { title: e.target.value })}
                  placeholder="显示文案（按钮上展示，≤8字，如：体检解读）"
                  maxLength={8}
                  showCount
                />
              </Space.Compact>
              <Input.TextArea
                rows={2}
                value={q.question}
                onChange={(e) => updateRQ(idx, { question: e.target.value })}
                placeholder="实际发送内容（点击后发给 AI 的完整提问，≤200字，可与显示文案不同）"
                maxLength={200}
                showCount
              />
            </Space>
          </Card>
        ))}
        <Button
          type="dashed"
          icon={<PlusOutlined />}
          block
          onClick={addRQ}
          disabled={cfg.recommended_questions.length >= 20}
        >
          新增推荐问 ({cfg.recommended_questions.length}/20)
        </Button>
      </Card>

      {/* Tab 3 · 功能宫格 7 字段 */}
      <Card
        id="anchor-func-grid"
        title="Tab 3 · 功能宫格（每项 7 字段，1~6 项）"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={() => saveModule('func_grid', cfg.func_grid)}
            >
              保存本节
            </Button>
          </Space>
        }
      >
        <Paragraph type="secondary">
          每项含主文案、副说明、跳转链接、图标、渐变色（起始+结束）、角标、是否启用 7 字段。最少 1 项、最多 6 项。
        </Paragraph>
        <Form layout="inline" style={{ marginBottom: 12 }}>
          <Form.Item label="布局列数">
            <Radio.Group
              value={cfg.func_grid.columns}
              onChange={(e) =>
                setCfg({ ...cfg, func_grid: { ...cfg.func_grid, columns: e.target.value } })
              }
            >
              <Radio value={2}>2 列</Radio>
              <Radio value={3}>3 列</Radio>
              <Radio value={4}>4 列</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
        {cfg.func_grid.items.length === 0 && <Empty description="至少 1 项" />}
        {cfg.func_grid.items.map((it, idx) => (
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
                  onChange={(c) => {
                    const list = [...cfg.func_grid.items];
                    list[idx] = { ...it, enabled: c };
                    setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                  }}
                  checkedChildren="启用"
                  unCheckedChildren="禁用"
                />
                <Button
                  size="small"
                  icon={<ArrowUpOutlined />}
                  disabled={idx === 0}
                  onClick={() => {
                    const list = [...cfg.func_grid.items];
                    [list[idx], list[idx - 1]] = [list[idx - 1], list[idx]];
                    list.forEach((x, i) => (x.sort = i + 1));
                    setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                  }}
                />
                <Button
                  size="small"
                  icon={<ArrowDownOutlined />}
                  disabled={idx === cfg.func_grid.items.length - 1}
                  onClick={() => {
                    const list = [...cfg.func_grid.items];
                    [list[idx], list[idx + 1]] = [list[idx + 1], list[idx]];
                    list.forEach((x, i) => (x.sort = i + 1));
                    setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                  }}
                />
                <Button
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  disabled={cfg.func_grid.items.length <= 1}
                  onClick={() => {
                    const list = cfg.func_grid.items.filter((_, i) => i !== idx);
                    setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                  }}
                />
              </Space>
            }
          >
            <Row gutter={12}>
              <Col span={8}>
                <Form.Item label="主文案（≤8字）">
                  <Input
                    value={it.main_text}
                    maxLength={8}
                    showCount
                    onChange={(e) => {
                      const list = [...cfg.func_grid.items];
                      list[idx] = { ...it, main_text: e.target.value };
                      setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                    }}
                    placeholder="如：AI诊室"
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="副说明（≤12字）">
                  <Input
                    value={it.sub_text}
                    maxLength={12}
                    showCount
                    onChange={(e) => {
                      const list = [...cfg.func_grid.items];
                      list[idx] = { ...it, sub_text: e.target.value };
                      setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                    }}
                    placeholder="如：智能问诊"
                  />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="跳转链接（/ 或 http(s)://）">
                  <Input
                    value={it.target_path}
                    onChange={(e) => {
                      const list = [...cfg.func_grid.items];
                      list[idx] = { ...it, target_path: e.target.value };
                      setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                    }}
                    placeholder="/ai-doctor"
                  />
                </Form.Item>
              </Col>
              <Col span={6}>
                <Form.Item label="图标（Emoji）">
                  <Input
                    value={it.icon}
                    maxLength={4}
                    onChange={(e) => {
                      const list = [...cfg.func_grid.items];
                      list[idx] = { ...it, icon: e.target.value };
                      setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                    }}
                    placeholder="🩺"
                  />
                </Form.Item>
              </Col>
              <Col span={6}>
                <Form.Item label="渐变起始色">
                  <Input
                    value={it.gradient_start}
                    onChange={(e) => {
                      const list = [...cfg.func_grid.items];
                      list[idx] = { ...it, gradient_start: e.target.value };
                      setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                    }}
                    placeholder="#5B6CFF"
                    addonAfter={
                      <input
                        type="color"
                        value={it.gradient_start}
                        onChange={(e) => {
                          const list = [...cfg.func_grid.items];
                          list[idx] = { ...it, gradient_start: e.target.value };
                          setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                        }}
                        style={{ width: 24, height: 24, border: 'none', padding: 0, background: 'transparent' }}
                      />
                    }
                  />
                </Form.Item>
              </Col>
              <Col span={6}>
                <Form.Item label="渐变结束色">
                  <Input
                    value={it.gradient_end}
                    onChange={(e) => {
                      const list = [...cfg.func_grid.items];
                      list[idx] = { ...it, gradient_end: e.target.value };
                      setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                    }}
                    placeholder="#8B9AFF"
                    addonAfter={
                      <input
                        type="color"
                        value={it.gradient_end}
                        onChange={(e) => {
                          const list = [...cfg.func_grid.items];
                          list[idx] = { ...it, gradient_end: e.target.value };
                          setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                        }}
                        style={{ width: 24, height: 24, border: 'none', padding: 0, background: 'transparent' }}
                      />
                    }
                  />
                </Form.Item>
              </Col>
              <Col span={6}>
                <Form.Item label="角标（≤4字，可空）">
                  <Input
                    value={it.badge || ''}
                    maxLength={4}
                    onChange={(e) => {
                      const list = [...cfg.func_grid.items];
                      list[idx] = { ...it, badge: e.target.value };
                      setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: list } });
                    }}
                    placeholder="如：NEW / HOT"
                  />
                </Form.Item>
              </Col>
            </Row>
            {/* 实时预览：渐变背景 */}
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
          disabled={cfg.func_grid.items.length >= 6}
          onClick={() => {
            const newItem: FuncGridItem = {
              main_text: '',
              sub_text: '',
              target_path: '/',
              icon: '✨',
              gradient_start: '#5B6CFF',
              gradient_end: '#8B9AFF',
              badge: '',
              enabled: true,
              sort: cfg.func_grid.items.length + 1,
            };
            setCfg({ ...cfg, func_grid: { ...cfg.func_grid, items: [...cfg.func_grid.items, newItem] } });
          }}
        >
          新增宫格项 ({cfg.func_grid.items.length}/6)
        </Button>
      </Card>

      {/* 4. 浮动按钮（Tab 6 · 全局开关 - 打卡按钮） */}
      <Card
        id="anchor-floating-button"
        title="Tab 6 · 浮动健康打卡按钮（4 字段精简版）"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button onClick={() => resetModule('floating_button')}>重置默认</Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={() => saveModule('floating_button', cfg.floating_button)}
            >
              保存本节
            </Button>
          </Space>
        }
      >
        <Form layout="vertical">
          <Form.Item label="是否显示">
            <Switch
              checked={cfg.floating_button.enabled}
              onChange={(c) =>
                setCfg({
                  ...cfg,
                  floating_button: { ...cfg.floating_button, enabled: c },
                })
              }
            />
          </Form.Item>
          <Form.Item label="图标 (emoji)">
            <Input
              style={{ width: 120 }}
              value={cfg.floating_button.icon}
              onChange={(e) =>
                setCfg({
                  ...cfg,
                  floating_button: { ...cfg.floating_button, icon: e.target.value },
                })
              }
              maxLength={4}
            />
          </Form.Item>
          <Form.Item label="按钮文字">
            <Input
              style={{ width: 240 }}
              value={cfg.floating_button.label || ''}
              onChange={(e) =>
                setCfg({
                  ...cfg,
                  floating_button: {
                    ...cfg.floating_button,
                    label: e.target.value,
                  },
                })
              }
              maxLength={10}
              placeholder="健康打卡"
            />
          </Form.Item>
          <Form.Item label="是否显示文字">
            <Switch
              checked={cfg.floating_button.show_label}
              onChange={(c) =>
                setCfg({
                  ...cfg,
                  floating_button: { ...cfg.floating_button, show_label: c },
                })
              }
            />
          </Form.Item>
          <Form.Item
            label="跳转路径（项目内）"
            extra="必须以 / 开头，禁止外链"
          >
            <Input
              style={{ width: 300 }}
              value={cfg.floating_button.target_path}
              onChange={(e) =>
                setCfg({
                  ...cfg,
                  floating_button: {
                    ...cfg.floating_button,
                    target_path: e.target.value,
                  },
                })
              }
              placeholder="/health-check-in"
            />
          </Form.Item>
          <Form.Item label="显示位置">
            <Radio.Group
              value={cfg.floating_button.position}
              onChange={(e) =>
                setCfg({
                  ...cfg,
                  floating_button: {
                    ...cfg.floating_button,
                    position: e.target.value,
                  },
                })
              }
            >
              <Radio value="right_bottom">右下</Radio>
              <Radio value="left_bottom">左下</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Card>

      {/* Tab 4 · 输入栏 */}
      <Card
        id="anchor-input"
        title="Tab 4 · 输入栏配置（含家庭成员咨询胶囊）"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button onClick={() => resetModule('input')}>重置默认</Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={() => saveModule('input', cfg.input)}
            >
              保存本节
            </Button>
          </Space>
        }
      >
        <Form layout="vertical">
          <Form.Item label="占位符文案">
            <Input
              value={cfg.input.placeholder}
              onChange={(e) =>
                setCfg({ ...cfg, input: { ...cfg.input, placeholder: e.target.value } })
              }
              maxLength={40}
            />
          </Form.Item>
          <Form.Item label="启用 🎤 语音输入按钮">
            <Switch
              checked={cfg.input.enable_voice}
              onChange={(c) =>
                setCfg({ ...cfg, input: { ...cfg.input, enable_voice: c } })
              }
            />
          </Form.Item>
          <Form.Item label="启用 AI 回复 TTS 播报按钮">
            <Switch
              checked={cfg.input.enable_tts}
              onChange={(c) =>
                setCfg({ ...cfg, input: { ...cfg.input, enable_tts: c } })
              }
            />
          </Form.Item>
          <Form.Item label="默认 TTS 提供方">
            <Select
              style={{ width: 180 }}
              value={cfg.input.tts_provider}
              onChange={(v) =>
                setCfg({ ...cfg, input: { ...cfg.input, tts_provider: v } })
              }
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
              checked={cfg.input.family_consult.enabled}
              onChange={(c) => setCfg({ ...cfg, input: { ...cfg.input, family_consult: { ...cfg.input.family_consult, enabled: c } } })}
            />
          </Form.Item>
          <Tooltip title="必须包含 {name} 占位符，将被替换为当前咨询对象姓名">
            <Form.Item label="胶囊默认文案模板（必含 {name}，≤20字）">
              <Input
                value={cfg.input.family_consult.template}
                onChange={(e) => setCfg({ ...cfg, input: { ...cfg.input, family_consult: { ...cfg.input.family_consult, template: e.target.value } } })}
                maxLength={20}
                showCount
                placeholder="为({name})咨询"
              />
            </Form.Item>
          </Tooltip>
          <Form.Item label="是否显示「查看档案」按钮">
            <Switch
              checked={cfg.input.family_consult.show_archive_link}
              onChange={(c) => setCfg({ ...cfg, input: { ...cfg.input, family_consult: { ...cfg.input.family_consult, show_archive_link: c } } })}
            />
          </Form.Item>
          <Form.Item label="查看档案跳转链接">
            <Input
              value={cfg.input.family_consult.archive_path}
              onChange={(e) => setCfg({ ...cfg, input: { ...cfg.input, family_consult: { ...cfg.input.family_consult, archive_path: e.target.value } } })}
              placeholder="/health-records"
            />
          </Form.Item>
        </Form>
      </Card>

      {/* Tab 5 · 会话策略（v1.0 新增 7 字段） */}
      <Card
        id="anchor-session-strategy"
        title="Tab 5 · 会话策略（7 个全局字段）"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={() => saveModule('session', cfg.session)}
            >
              保存本节
            </Button>
          </Space>
        }
      >
        <Form layout="vertical">
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="单次回答最大字数（100~5000）">
                <InputNumber
                  min={100}
                  max={5000}
                  value={cfg.session.strategy.max_answer_chars}
                  onChange={(v) =>
                    setCfg({ ...cfg, session: { ...cfg.session, strategy: { ...cfg.session.strategy, max_answer_chars: Number(v) || 1000 } } })
                  }
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="单日免费提问次数上限（1~999）">
                <InputNumber
                  min={1}
                  max={999}
                  value={cfg.session.strategy.daily_free_quota}
                  onChange={(v) =>
                    setCfg({ ...cfg, session: { ...cfg.session, strategy: { ...cfg.session.strategy, daily_free_quota: Number(v) || 50 } } })
                  }
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="上下文记忆轮数">
                <Select
                  value={cfg.session.strategy.context_memory_rounds}
                  onChange={(v) =>
                    setCfg({ ...cfg, session: { ...cfg.session, strategy: { ...cfg.session.strategy, context_memory_rounds: v } } })
                  }
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
              value={cfg.session.strategy.answer_style}
              onChange={(e) =>
                setCfg({ ...cfg, session: { ...cfg.session, strategy: { ...cfg.session.strategy, answer_style: e.target.value } } })
              }
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
                  checked={cfg.session.strategy.show_loading}
                  onChange={(c) =>
                    setCfg({ ...cfg, session: { ...cfg.session, strategy: { ...cfg.session.strategy, show_loading: c } } })
                  }
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="敏感词过滤开关">
                <Switch
                  checked={cfg.session.strategy.sensitive_filter}
                  onChange={(c) =>
                    setCfg({ ...cfg, session: { ...cfg.session, strategy: { ...cfg.session.strategy, sensitive_filter: c } } })
                  }
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="免责声明文案（≤100字，每次回答末尾自动追加）">
            <Input.TextArea
              rows={2}
              value={cfg.session.strategy.disclaimer}
              maxLength={100}
              showCount
              onChange={(e) =>
                setCfg({ ...cfg, session: { ...cfg.session, strategy: { ...cfg.session.strategy, disclaimer: e.target.value } } })
              }
              placeholder="以上内容仅供参考，不能替代医生诊疗"
            />
          </Form.Item>
        </Form>
      </Card>

      {/* 6. 会话策略（旧）- 空闲超时 */}
      <Card
        id="anchor-session"
        title="Tab 5 · 空闲超时与空会话引导"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button onClick={() => resetModule('session')}>重置默认</Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={() => saveModule('session', cfg.session)}
            >
              保存本节
            </Button>
          </Space>
        }
      >
        <Form layout="vertical">
          <Form.Item
            label="空闲超时分钟数"
            extra="与现有 chat-idle-timeout 接口共用同一存储"
          >
            <InputNumber
              min={1}
              max={1440}
              value={cfg.session.idle_timeout_minutes}
              onChange={(v) =>
                setCfg({
                  ...cfg,
                  session: { ...cfg.session, idle_timeout_minutes: Number(v) || 30 },
                })
              }
            />
          </Form.Item>
          <Form.Item label="启用空闲自动新会话">
            <Switch
              checked={cfg.session.auto_new_session}
              onChange={(c) =>
                setCfg({ ...cfg, session: { ...cfg.session, auto_new_session: c } })
              }
            />
          </Form.Item>
          <Divider plain>空会话引导（H5 端目前没有，本期新增）</Divider>
          <Form.Item label="进入空会话时自动播放 AI 欢迎语">
            <Switch
              checked={cfg.session.empty_session_welcome.enabled}
              onChange={(c) =>
                setCfg({
                  ...cfg,
                  session: {
                    ...cfg.session,
                    empty_session_welcome: {
                      ...cfg.session.empty_session_welcome,
                      enabled: c,
                    },
                  },
                })
              }
            />
          </Form.Item>
          <Form.Item label="欢迎语内容（多条随机抽 1）">
            <StringListEditor
              value={cfg.session.empty_session_welcome.messages}
              onChange={(v) =>
                setCfg({
                  ...cfg,
                  session: {
                    ...cfg.session,
                    empty_session_welcome: {
                      ...cfg.session.empty_session_welcome,
                      messages: v,
                    },
                  },
                })
              }
              placeholder="例如：你好，我是你的 AI 健康助手"
              max={20}
            />
          </Form.Item>
        </Form>
      </Card>

      {/* Tab 6 · 全局开关（9 个总开关） */}
      <Card
        id="anchor-global-switches"
        title="Tab 6 · 全局开关（9 个模块级总开关）"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={() => saveModule('global_switches', cfg.global_switches)}
            >
              保存本节
            </Button>
          </Space>
        }
      >
        <Paragraph type="secondary">
          子项级开关（如功能宫格里某一项是否显示、推荐问某一条是否显示）由各项内部的「是否启用」字段承担。本卡片只放<strong>模块级</strong>开关。与对应字段 Tab 内的「是否启用」联动取并集——只要其中一处关闭，模块即不显示。
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
                  checked={(cfg.global_switches as any)[item.key]}
                  onChange={(c) =>
                    setCfg({ ...cfg, global_switches: { ...cfg.global_switches, [item.key]: c } as GlobalSwitches })
                  }
                />
              </Form.Item>
            </Col>
          ))}
        </Row>
      </Card>

      {/* 7. Banner / 宫格 / 标签条显隐（兼容旧字段） */}
      <Card
        id="anchor-banner"
        title="补充 · Banner / 标签条 显隐（兼容旧字段）"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={async () => {
                await saveModule('banner', cfg.banner);
                await saveModule('func_grid', cfg.func_grid);
                await saveModule('quick_tags', cfg.quick_tags);
              }}
            >
              保存本节
            </Button>
          </Space>
        }
      >
        <Paragraph type="secondary">
          Banner / 功能宫格 / 快捷标签条的<strong>内容</strong>
          仍由原有「首页 Banner」/「功能按钮」后台模块管理，本卡片只控制是否显示和显示规模。
        </Paragraph>
        <Form layout="vertical">
          <Form.Item label="在 AI 首页显示 Banner">
            <Switch
              checked={cfg.banner.visible}
              onChange={(c) => setCfg({ ...cfg, banner: { visible: c } })}
            />
          </Form.Item>
          <Form.Item label="显示功能宫格">
            <Switch
              checked={cfg.func_grid.visible}
              onChange={(c) =>
                setCfg({ ...cfg, func_grid: { ...cfg.func_grid, visible: c } })
              }
            />
          </Form.Item>
          <Form.Item label="宫格列数">
            <Radio.Group
              value={cfg.func_grid.columns}
              onChange={(e) =>
                setCfg({
                  ...cfg,
                  func_grid: { ...cfg.func_grid, columns: e.target.value },
                })
              }
            >
              <Radio value={2}>2 列</Radio>
              <Radio value={3}>3 列</Radio>
              <Radio value={4}>4 列</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item label="宫格最多展示数量">
            <InputNumber
              min={1}
              max={12}
              value={cfg.func_grid.max_count}
              onChange={(v) =>
                setCfg({
                  ...cfg,
                  func_grid: { ...cfg.func_grid, max_count: Number(v) || 6 },
                })
              }
            />
          </Form.Item>
          <Form.Item label="显示底部快捷标签条">
            <Switch
              checked={cfg.quick_tags.visible}
              onChange={(c) =>
                setCfg({ ...cfg, quick_tags: { ...cfg.quick_tags, visible: c } })
              }
            />
          </Form.Item>
          <Form.Item label="底部快捷标签最多展示数量">
            <InputNumber
              min={1}
              max={16}
              value={cfg.quick_tags.max_count}
              onChange={(v) =>
                setCfg({
                  ...cfg,
                  quick_tags: { ...cfg.quick_tags, max_count: Number(v) || 8 },
                })
              }
            />
          </Form.Item>
        </Form>
      </Card>

      {/* 底部全部保存 */}
      <Card style={{ marginBottom: 24, position: 'sticky', bottom: 0, zIndex: 5 }}>
        <Space>
          <Button onClick={fetchConfig} icon={<ReloadOutlined />}>
            放弃修改
          </Button>
          <Button
            type="primary"
            size="large"
            icon={<SaveOutlined />}
            onClick={saveAll}
            loading={saving}
          >
            全部保存
          </Button>
        </Space>
      </Card>
    </Spin>
  );
}
