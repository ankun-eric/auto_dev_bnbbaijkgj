'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Table, Button, Space, Tag, Switch, Modal, Form, Input, Select,
  InputNumber, Typography, message, Empty,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SmileOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
// [AICHAT-OPTIM-FIX-V1 F-01 2026-05-14] 接入公共 EmojiPicker（与首页菜单管理同一套组件）
import { EmojiPickerModal } from '@/components/EmojiPicker';

const { Title } = Typography;
const { TextArea } = Input;

// [PRD-PROMPT-CONFIG-V1 2026-05-14] 按钮类型枚举（8 种，新增 report_interpret 报告解读专属类型）
const BUTTON_TYPE_OPTIONS = [
  { value: 'digital_human_call', label: '📞 数字人通话' },
  { value: 'photo_upload', label: '📷 拍照上传（通用素材）' },
  { value: 'file_upload', label: '📄 文件上传（通用素材）' },
  { value: 'report_interpret', label: '🩺 报告解读（体检报告专属）' },
  { value: 'photo_recognize_drug', label: '🔍 拍照识药' },
  { value: 'ai_chat_trigger', label: '💬 AI对话触发' },
  { value: 'quick_ask', label: '⚡ 快捷提问' },
  { value: 'external_link', label: '🔗 外部链接' },
];

const BUTTON_TYPE_MAP: Record<string, { label: string; color: string }> = {
  digital_human_call: { label: '数字人通话', color: 'blue' },
  photo_upload: { label: '拍照上传', color: 'green' },
  file_upload: { label: '文件上传', color: 'orange' },
  report_interpret: { label: '报告解读', color: 'volcano' },
  ai_chat_trigger: { label: 'AI对话触发', color: 'purple' },
  external_link: { label: '外部链接', color: 'default' },
  photo_recognize_drug: { label: '拍照识药', color: 'cyan' },
  quick_ask: { label: '快捷提问', color: 'magenta' },
  // 兼容旧值
  ai_dialog_trigger: { label: 'AI对话触发(旧)', color: 'purple' },
  drug_identify: { label: '拍照识药(旧)', color: 'cyan' },
};

// 需要关联 Prompt 模板的按钮类型（PRD §3.2 + PRD-PROMPT-CONFIG-V1）
// [PRD-AICHAT-CAPSULE-V2 2026-05-15] photo_recognize_drug 现仅使用「关联 Prompt 模板」，
// 不再保留独立的「AI 回复模式」字段；3 档语义由系统内置的 3 个识药 Prompt 模板承载。
const PROMPT_TEMPLATE_REQUIRED_TYPES = new Set([
  'ai_chat_trigger',
  'photo_recognize_drug',
  'report_interpret',
]);

interface FunctionButton {
  id: number;
  name: string;
  icon_url: string;
  // [AICHAT-OPTIM-FIX-V1 F-01] Emoji 图标字段（取代 icon_url 作为主图标存储）
  icon?: string;
  button_type: string;
  sort_weight: number;
  is_enabled: boolean;
  params: any;
  // [AI对话模式优化 PRD v1.0] 8 个新字段
  prompt_template_id?: number | null;
  external_url?: string | null;
  preset_prompt?: string | null;
  auto_user_message?: string;
  card_title?: string;
  card_subtitle?: string | null;
  card_cover_image?: string | null;
  button_sub_desc?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface PromptTemplateOption {
  value: number;
  label: string;
  promptType?: string;
  businessGroup?: string;
  allowedButtonTypes: string[];
}

export default function FunctionButtonsPage() {
  const router = useRouter();
  const [items, setItems] = useState<FunctionButton[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<FunctionButton | null>(null);
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [form] = Form.useForm();
  const watchedButtonType = Form.useWatch('button_type', form);
  const watchedName = Form.useWatch('name', form);
  const watchedIcon = Form.useWatch('icon', form);
  const [promptOptions, setPromptOptions] = useState<PromptTemplateOption[]>([]);
  // [AICHAT-OPTIM-FIX-V1 F-01] Emoji 选择器弹窗状态
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false);

  // [PRD-PROMPT-CONFIG-V1 2026-05-14] 修复"下拉永远为空" Bug：
  // 后端返回的是 GroupResponse 列表 [{prompt_type, display_name, active_template:{id,name,...}, business_group, allowed_button_types}]
  // 此前错误读取 it.id / it.is_active，导致 .filter 全部丢弃 → 永远 0 项
  // 正确做法：遍历 groups，从 active_template 拿 id，并保留 business_group + allowed_button_types 用于联动过滤
  const fetchPromptTemplates = useCallback(async () => {
    try {
      const res = await get<any>('/api/admin/prompt-templates');
      const groups = Array.isArray(res) ? res : (res?.items || []);
      const options: PromptTemplateOption[] = [];
      groups.forEach((g: any) => {
        const tpl = g?.active_template;
        if (!tpl || !tpl.id || tpl.is_active === false) return;
        options.push({
          value: tpl.id,
          label: `${g.display_name || tpl.name || tpl.prompt_type}`,
          promptType: g.prompt_type,
          businessGroup: g.business_group,
          allowedButtonTypes: Array.isArray(g.allowed_button_types) ? g.allowed_button_types : [],
        });
      });
      setPromptOptions(options);
    } catch {
      // 静默失败：Prompt 列表加载失败不阻塞按钮管理
      setPromptOptions([]);
    }
  }, []);

  // 联动过滤：根据当前选中的 button_type 过滤可绑定 Prompt
  const filteredPromptOptions = useMemo(() => {
    if (!watchedButtonType) return promptOptions;
    return promptOptions.filter((o) =>
      // 配置缺失（无 allowed_button_types）时不阻断
      !o.allowedButtonTypes || o.allowedButtonTypes.length === 0 || o.allowedButtonTypes.includes(watchedButtonType),
    );
  }, [promptOptions, watchedButtonType]);

  useEffect(() => {
    fetchPromptTemplates();
  }, [fetchPromptTemplates]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/function-buttons', { page, page_size: pageSize });
      if (Array.isArray(res)) {
        setItems(res);
        setTotal(res.length);
      } else {
        setItems(res.items || []);
        setTotal(res.total || 0);
      }
    } catch {
      message.error('获取功能按钮列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenModal = (record?: FunctionButton) => {
    setEditingItem(record || null);
    form.resetFields();
    if (record) {
      const parsedParams = typeof record.params === 'string'
        ? (() => { try { return JSON.parse(record.params); } catch { return null; } })()
        : record.params;

      const formValues: Record<string, any> = {
        name: record.name,
        icon_url: record.icon_url,
        // [AICHAT-OPTIM-FIX-V1 F-01] icon Emoji 字段（兜底用 icon_url 回填以兼容历史数据）
        icon: record.icon || (record.icon_url && record.icon_url.length <= 4 ? record.icon_url : '') || '📌',
        button_type: record.button_type,
        sort_weight: record.sort_weight,
        is_enabled: record.is_enabled,
        params: record.params
          ? (typeof record.params === 'string' ? record.params : JSON.stringify(record.params, null, 2))
          : '',
        // [AI对话模式优化 PRD v1.0] 8 个新字段回填
        prompt_template_id: record.prompt_template_id || undefined,
        external_url: record.external_url || '',
        preset_prompt: record.preset_prompt || '',
        auto_user_message: record.auto_user_message || '',
        card_title: record.card_title || '',
        card_subtitle: record.card_subtitle || '',
        card_cover_image: record.card_cover_image || '',
        button_sub_desc: record.button_sub_desc || '',
      };

      // [PRD-AICHAT-CAPSULE-V2 2026-05-15] 移除 ai_reply_mode 字段回填（统一由「关联 Prompt 模板」承载）；
      // 保留 photo_tip_text / max_photo_count 用于拍照交互细节
      if ((record.button_type === 'photo_recognize_drug' || record.button_type === 'drug_identify') && parsedParams) {
        formValues.photo_tip_text = parsedParams.photo_tip_text || '请确保药品名称、品牌、规格完整，拍摄清晰';
        formValues.max_photo_count = parsedParams.max_photo_count ?? 5;
      }

      form.setFieldsValue(formValues);
    } else {
      form.setFieldsValue({
        is_enabled: true,
        sort_weight: 0,
        photo_tip_text: '请确保药品名称、品牌、规格完整，拍摄清晰',
        max_photo_count: 5,
        auto_user_message: '',
        card_title: '',
        icon: '📌',
      });
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      let parsedParams = values.params;
      if (parsedParams && typeof parsedParams === 'string') {
        try {
          parsedParams = JSON.parse(parsedParams);
        } catch {
          parsedParams = values.params;
        }
      }

      // [PRD-AICHAT-CAPSULE-V2 2026-05-15] 不再写 ai_reply_mode；保留 photo_tip_text / max_photo_count
      let finalParams = parsedParams || null;
      if (values.button_type === 'photo_recognize_drug' || values.button_type === 'drug_identify') {
        const base = (typeof finalParams === 'object' && finalParams) ? finalParams : {};
        finalParams = {
          ...base,
          photo_tip_text: values.photo_tip_text || '请确保药品名称、品牌、规格完整，拍摄清晰',
          max_photo_count: values.max_photo_count ?? 5,
        };
      }

      const payload: Record<string, any> = {
        name: values.name,
        icon_url: values.icon_url,
        // [AICHAT-OPTIM-FIX-V1 F-01] icon Emoji 字段
        icon: values.icon || '📌',
        button_type: values.button_type,
        sort_weight: values.sort_weight ?? 0,
        is_enabled: values.is_enabled,
        params: finalParams,
        // [AI对话模式优化 PRD v1.0] 8 个新字段（按类型条件传）
        prompt_template_id: PROMPT_TEMPLATE_REQUIRED_TYPES.has(values.button_type)
          ? (values.prompt_template_id || null)
          : null,
        external_url: values.button_type === 'external_link' ? (values.external_url || null) : null,
        preset_prompt: values.button_type === 'quick_ask' ? (values.preset_prompt || null) : null,
        auto_user_message: values.auto_user_message || '',
        card_title: values.card_title || '',
        card_subtitle: values.card_subtitle || null,
        // [PRD-AICHAT-CAPSULE-V2 2026-05-15] 不再编辑「卡片封面图 URL」，前端永远传 null（后端兼容接收）
        card_cover_image: null,
        button_sub_desc: values.button_sub_desc || null,
      };

      if (editingItem) {
        await put(`/api/admin/function-buttons/${editingItem.id}`, payload);
        message.success('功能按钮更新成功');
      } else {
        await post('/api/admin/function-buttons', payload);
        message.success('功能按钮创建成功');
      }
      setModalOpen(false);
      fetchData();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = (record: FunctionButton) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除功能按钮「${record.name}」吗？`,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await del(`/api/admin/function-buttons/${record.id}`);
          message.success('删除成功');
          fetchData();
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '删除失败');
        }
      },
    });
  };

  const handleToggleEnabled = async (record: FunctionButton, checked: boolean) => {
    try {
      await put(`/api/admin/function-buttons/${record.id}`, { is_enabled: checked });
      message.success('状态更新成功');
      fetchData();
    } catch {
      message.error('状态更新失败');
    }
  };

  const columns = [
    {
      title: '排序权重',
      dataIndex: 'sort_weight',
      key: 'sort_weight',
      width: 100,
      sorter: (a: FunctionButton, b: FunctionButton) => a.sort_weight - b.sort_weight,
    },
    {
      title: '图标',
      // [AICHAT-OPTIM-FIX-V1 F-01] 图标列改为显示 Emoji 字符（24px 字号）
      dataIndex: 'icon',
      key: 'icon',
      width: 80,
      render: (val: string, record: FunctionButton) => {
        // 优先 icon 字段；为空时兜底使用 📌
        const emoji = val || record.icon || '📌';
        return <span style={{ fontSize: 24, display: 'inline-block', minWidth: 32, textAlign: 'center' }}>{emoji}</span>;
      },
    },
    {
      title: '按钮名称',
      dataIndex: 'name',
      key: 'name',
      width: 140,
    },
    {
      title: '按钮类型',
      dataIndex: 'button_type',
      key: 'button_type',
      width: 130,
      render: (val: string) => {
        const info = BUTTON_TYPE_MAP[val];
        return info ? <Tag color={info.color}>{info.label}</Tag> : <Tag>{val}</Tag>;
      },
    },
    {
      title: '启用状态',
      dataIndex: 'is_enabled',
      key: 'is_enabled',
      width: 100,
      render: (val: boolean, record: FunctionButton) => (
        <Switch
          checked={val}
          checkedChildren="启用"
          unCheckedChildren="禁用"
          onChange={(checked) => handleToggleEnabled(record, checked)}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: FunctionButton) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
          </Button>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>功能按钮管理</Title>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          新增按钮
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={items}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
        scroll={{ x: 800 }}
      />
      <Modal
        title={editingItem ? '编辑功能按钮' : '新增功能按钮'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical" initialValues={{ is_enabled: true, sort_weight: 0 }}>
          <Form.Item
            label="按钮名称"
            name="name"
            rules={[{ required: true, message: '请输入按钮名称' }]}
          >
            <Input placeholder="请输入按钮名称" maxLength={20} />
          </Form.Item>
          {/* [AICHAT-OPTIM-FIX-V1 F-01] 图标 Emoji 选择器（取代 icon_url 图片 URL） */}
          <Form.Item
            label="按钮图标（Emoji）"
            name="icon"
            rules={[
              { required: true, message: '请选择按钮 Emoji 图标' },
              {
                validator: (_, value) => {
                  if (!value) return Promise.resolve();
                  // 字符串长度允许 1~16（兼容 ZWJ 序列 emoji 如 👨‍⚕️ / 👨‍👩‍👧‍👦）
                  if (value.length >= 1 && value.length <= 16) return Promise.resolve();
                  return Promise.reject(new Error('请选择 1 个 Emoji 字符'));
                },
              },
            ]}
            extra="点击下方按钮打开 Emoji 选择器（支持关键字推荐）"
          >
            <Input.Group compact data-testid="function-button-icon-picker">
              <Input
                style={{ width: 'calc(100% - 120px)', textAlign: 'center', fontSize: 24 }}
                placeholder="点击右侧按钮选择 Emoji"
                readOnly
                value={watchedIcon || ''}
              />
              <Button
                type="primary"
                icon={<SmileOutlined />}
                style={{ width: 120 }}
                onClick={() => setEmojiPickerOpen(true)}
              >
                选择 Emoji
              </Button>
            </Input.Group>
          </Form.Item>
          {/* 保留 icon_url 隐藏字段以兼容旧数据写回（admin 不再编辑图片 URL） */}
          <Form.Item name="icon_url" hidden>
            <Input />
          </Form.Item>
          <Form.Item
            label="按钮类型"
            name="button_type"
            rules={[{ required: true, message: '请选择按钮类型' }]}
          >
            <Select placeholder="请选择按钮类型" options={BUTTON_TYPE_OPTIONS} />
          </Form.Item>
          {/* [PRD-AICHAT-CAPSULE-V2 2026-05-15] 拍照识药保留拍照参数，但不再有「AI 回复模式」字段；
              AI 行为统一由下方「关联 Prompt 模板」承载（系统内置 3 个识药模板可选） */}
          {(watchedButtonType === 'photo_recognize_drug' || watchedButtonType === 'drug_identify') && (
            <>
              <Form.Item label="拍照提示语" name="photo_tip_text">
                <Input placeholder="请确保药品名称、品牌、规格完整，拍摄清晰" />
              </Form.Item>
              <Form.Item label="最大图片数" name="max_photo_count">
                <InputNumber min={1} max={10} style={{ width: '100%' }} placeholder="默认5张" />
              </Form.Item>
            </>
          )}
          {/* [PRD-PROMPT-CONFIG-V1 2026-05-14] 关联 Prompt 模板（仅部分类型显示） + 联动过滤 + 空状态跳转 */}
          {watchedButtonType && PROMPT_TEMPLATE_REQUIRED_TYPES.has(watchedButtonType) && (
            <Form.Item
              label="关联 Prompt 模板"
              name="prompt_template_id"
              rules={[{ required: true, message: '请选择关联 Prompt 模板' }]}
              extra="数据源：AI 配置中心 → Prompt 模板配置（已按按钮类型过滤）"
            >
              <Select
                placeholder="请选择 Prompt 模板"
                options={filteredPromptOptions}
                showSearch
                allowClear
                filterOption={(input, option) =>
                  String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                }
                notFoundContent={
                  <div style={{ padding: 12, textAlign: 'center' }} data-testid="prompt-empty-state">
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description="当前按钮类型暂无可用 Prompt 模板"
                    />
                    <Button
                      type="link"
                      size="small"
                      onClick={() => router.push('/prompt-templates')}
                    >
                      去 Prompt 配置中心 →
                    </Button>
                  </div>
                }
              />
            </Form.Item>
          )}
          {/* 外部链接 URL（仅 external_link） */}
          {watchedButtonType === 'external_link' && (
            <Form.Item
              label="外部链接 URL"
              name="external_url"
              rules={[{ required: true, message: '请输入外部链接 URL' }]}
            >
              <Input placeholder="例：https://example.com 或 /services 或 webview://..." />
            </Form.Item>
          )}
          {/* 预设话术（仅 quick_ask） */}
          {watchedButtonType === 'quick_ask' && (
            <Form.Item
              label="预设话术"
              name="preset_prompt"
              rules={[{ required: true, message: '请输入预设话术（点击后作为用户消息发给 AI）' }]}
            >
              <TextArea rows={3} placeholder="例：我想了解高血压日常注意事项有哪些？" maxLength={500} showCount />
            </Form.Item>
          )}
          {/* 通用 8 字段：所有类型可填 */}
          <Form.Item
            label="自动用户消息"
            name="auto_user_message"
            rules={[{ required: true, message: '请输入点击后插入对话流的用户消息' }]}
            extra="点击按钮后插入对话流的用户气泡文案，例：我想做体质测评"
          >
            <Input placeholder="例：我想做体质测评" maxLength={200} />
          </Form.Item>
          <Form.Item
            label="卡片标题"
            name="card_title"
            rules={[{ required: true, message: '请输入卡片标题' }]}
          >
            <Input placeholder="卡片头部主标题" maxLength={50} />
          </Form.Item>
          <Form.Item label="卡片副标题" name="card_subtitle">
            <Input placeholder="卡片头部副标题（可选）" maxLength={100} />
          </Form.Item>
          {/* [PRD-AICHAT-CAPSULE-V2 2026-05-15] 移除「卡片封面图 URL」字段（用户端统一改为 Emoji + 主题色背景渲染） */}
          <Form.Item label="按钮副说明文字" name="button_sub_desc" extra="显示在卡片主按钮下方，例：约 6 道题，2 分钟完成">
            <Input placeholder="按钮副说明（可选）" maxLength={100} />
          </Form.Item>
          <Form.Item label="排序权重" name="sort_weight">
            <InputNumber min={0} max={9999} style={{ width: '100%' }} placeholder="数值越大越靠前" />
          </Form.Item>
          <Form.Item label="启用状态" name="is_enabled" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
          <Form.Item label="关联参数" name="params">
            <TextArea rows={4} placeholder='请输入JSON格式参数，例如: {"url": "https://..."}' />
          </Form.Item>
        </Form>
      </Modal>

      {/* [AICHAT-OPTIM-FIX-V1 F-01] Emoji 选择器弹窗（与首页菜单管理同一套组件） */}
      <EmojiPickerModal
        open={emojiPickerOpen}
        defaultEmoji={watchedIcon || ''}
        menuName={watchedName || ''}
        onOk={(emoji) => {
          form.setFieldsValue({ icon: emoji });
          setEmojiPickerOpen(false);
        }}
        onCancel={() => setEmojiPickerOpen(false)}
      />
    </div>
  );
}
