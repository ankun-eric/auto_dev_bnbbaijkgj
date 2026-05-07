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
  title: string;
  question: string;
  enabled: boolean;
  sort: number;
};
type Cfg = {
  welcome: {
    avatar: AvatarObj;
    greetings: { morning: string[]; afternoon: string[]; evening: string[] };
    subtitles: string[];
    show_nickname: boolean;
  };
  topbar: {
    title: string;
    logo: AvatarObj;
    show_sidebar: boolean;
    show_more_menu: boolean;
    show_share: boolean;
  };
  input: {
    placeholder: string;
    enable_voice: boolean;
    enable_tts: boolean;
    tts_provider: 'auto' | 'cloud' | 'browser';
  };
  session: {
    idle_timeout_minutes: number;
    auto_new_session: boolean;
    empty_session_welcome: { enabled: boolean; messages: string[] };
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
  func_grid: { visible: boolean; columns: 2 | 3 | 4; max_count: number };
  quick_tags: { visible: boolean; max_count: number };
  recommended_questions: RecommendedQ[];
};

const DEFAULT_CFG: Cfg = {
  welcome: {
    avatar: { type: 'emoji', emoji: '🌿' },
    greetings: { morning: ['早上好'], afternoon: ['午安'], evening: ['晚上好'] },
    subtitles: ['有什么健康问题想问我?'],
    show_nickname: true,
  },
  topbar: {
    title: 'AI 健康助手',
    logo: { type: 'emoji', emoji: '🌿' },
    show_sidebar: true,
    show_more_menu: true,
    show_share: true,
  },
  input: {
    placeholder: '问问健康助手...',
    enable_voice: true,
    enable_tts: true,
    tts_provider: 'auto',
  },
  session: {
    idle_timeout_minutes: 30,
    auto_new_session: true,
    empty_session_welcome: { enabled: false, messages: [] },
  },
  floating_button: {
    enabled: true,
    icon: '✅',
    label: '健康打卡',
    show_label: false,
    target_path: '/health-check-in',
    position: 'right_bottom',
  },
  banner: { visible: true },
  func_grid: { visible: true, columns: 3, max_count: 6 },
  quick_tags: { visible: true, max_count: 8 },
  recommended_questions: [],
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

      {/* 1. 欢迎区 */}
      <Card
        title="1. 欢迎区配置"
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
          <Form.Item label="头像">
            <AvatarEditor
              value={cfg.welcome.avatar}
              onChange={(v) =>
                setCfg({ ...cfg, welcome: { ...cfg.welcome, avatar: v } })
              }
              uploadAction={upload}
            />
          </Form.Item>
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

      {/* 2. 顶栏与品牌 */}
      <Card
        title="2. 顶栏与品牌配置"
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

      {/* 3. 推荐问 */}
      <Card
        title='3. 推荐问列表配置（"试着问我"卡片）'
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
                  placeholder="🩺"
                />
                <Input
                  style={{ flex: 1 }}
                  value={q.title}
                  onChange={(e) => updateRQ(idx, { title: e.target.value })}
                  placeholder="卡片主标题（如：健康咨询）"
                />
              </Space.Compact>
              <Input.TextArea
                rows={2}
                value={q.question}
                onChange={(e) => updateRQ(idx, { question: e.target.value })}
                placeholder="实际发送的提问文本"
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

      {/* 4. 浮动按钮 */}
      <Card
        title="4. 浮动健康打卡按钮配置"
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

      {/* 5. 输入栏 */}
      <Card
        title="5. 输入栏配置"
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
        </Form>
      </Card>

      {/* 6. 会话策略 */}
      <Card
        title="6. 空闲超时与会话策略"
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

      {/* 7. Banner / 宫格 / 标签条显隐 */}
      <Card
        title="7. Banner / 功能宫格 / 底部快捷标签条 显隐配置"
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
