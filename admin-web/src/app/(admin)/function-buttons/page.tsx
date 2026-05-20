'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Table, Button, Space, Tag, Switch, Modal, Form, Input, Select,
  InputNumber, Typography, message, Empty, Tabs,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, SmileOutlined,
  VerticalAlignTopOutlined, ArrowUpOutlined, ArrowDownOutlined,
} from '@ant-design/icons';
import { get, post, put, del, patch } from '@/lib/api';
// [AICHAT-OPTIM-FIX-V1 F-01 2026-05-14] 接入公共 EmojiPicker（与首页菜单管理同一套组件）
import { EmojiPickerModal } from '@/components/EmojiPicker';
// [PRD-AICHAT-FUNCCARD-V2 2026-05-20] 卡片预览浮层组件
import FunctionCardV2Preview, { PhonePreviewFrame } from '@/components/FunctionCardV2Preview';
import { EyeOutlined } from '@ant-design/icons';

const { Title } = Typography;
const { TextArea } = Input;

// [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 主类型简化为两大类：页面跳转 / AI 功能
const MAIN_TYPE_OPTIONS = [
  { value: 'page_navigate', label: '🔗 页面跳转（外部链接 / 内部页面）' },
  { value: 'ai_function', label: '🤖 AI 功能' },
];

// [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19]
// AI 功能子类型升级：永久稳定 5 个（按"交互形态"抽象，不再随业务膨胀）
// - questionnaire   : 对话内问卷（由 questionnaire_template_id 区分业务）
// - image_capture   : 图像采集（由 capture_purpose 区分识药/上传/报告解读）
// - file_upload     : 文件上传
// - ai_dialog_trigger : AI 对话触发
// - quick_ask       : 快捷提问
// 旧的 photo_upload / report_interpret / medicine_recognize / health_self_check
// 由数据迁移自动归类，前端不再展示这些选项（编辑老数据时也会自动映射到新枚举）
const AI_FUNCTION_TYPE_OPTIONS = [
  { value: 'questionnaire', label: '📝 对话内问卷（健康自查 / 体质测评 / 睡眠测评等）' },
  { value: 'image_capture', label: '📷 图像采集（识药 / 上传 / 报告解读）' },
  { value: 'file_upload', label: '📄 文件上传' },
  { value: 'ai_dialog_trigger', label: '💬 AI 对话触发' },
  { value: 'quick_ask', label: '⚡ 快捷提问' },
];

// [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1] 图像采集子用途
const CAPTURE_PURPOSE_OPTIONS = [
  { value: 'identify_medicine', label: '🔍 识药（相册/拍照 → AI 识药）' },
  { value: 'upload', label: '📤 纯上传（相册/拍照 → 直接发图）' },
  { value: 'interpret_report', label: '🩺 报告解读（相册/拍照/历史报告 → AI 解读）' },
];

// [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 问卷展示形态
const QUESTIONNAIRE_DISPLAY_FORM_OPTIONS = [
  { value: 'DRAWER_SCROLL', label: '🪟 抽屉-一屏多题（健康自查）' },
  { value: 'DRAWER_STEPPED', label: '📑 抽屉-一题一屏（体质测评）' },
  { value: 'INLINE_CHAT', label: '💬 对话内插入（轻量问卷）' },
];

// [PRD-PROMPT-CONFIG-V1 2026-05-14] 老 9 种枚举（保留下拉以兼容编辑老数据；
// 新建/迁移后的按钮统一从 MAIN_TYPE_OPTIONS 选择）
const BUTTON_TYPE_OPTIONS = [
  ...MAIN_TYPE_OPTIONS,
  { value: 'digital_human_call', label: '（兼容）📞 数字人通话' },
  { value: 'photo_upload', label: '（兼容）📷 拍照上传' },
  { value: 'file_upload', label: '（兼容）📄 文件上传' },
  { value: 'report_interpret', label: '（兼容）🩺 报告解读' },
  { value: 'photo_recognize_drug', label: '（兼容）🔍 拍照识药' },
  { value: 'ai_chat_trigger', label: '（兼容）💬 AI对话触发' },
  { value: 'quick_ask', label: '（兼容）⚡ 快捷提问' },
  { value: 'external_link', label: '（兼容）🔗 外部链接' },
  { value: 'health_self_check', label: '（兼容）🏥 健康自查（抽屉问卷）' },
];

// [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 未选档案策略
const ARCHIVE_MISSING_STRATEGY_OPTIONS = [
  { value: 'use_default', label: '使用默认档案（推荐）' },
  { value: 'prompt_on_submit', label: '提交时再提示选择' },
  { value: 'force_toast', label: '强制 toast 先选档案' },
];

const BUTTON_TYPE_MAP: Record<string, { label: string; color: string }> = {
  // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 新两大类
  page_navigate: { label: '页面跳转', color: 'geekblue' },
  ai_function: { label: 'AI 功能', color: 'cyan' },
  // ─── 老枚举（迁移期内仍然可能短暂出现，自动映射后会被覆盖） ───
  digital_human_call: { label: '数字人通话', color: 'blue' },
  photo_upload: { label: '拍照上传', color: 'green' },
  file_upload: { label: '文件上传', color: 'orange' },
  report_interpret: { label: '报告解读', color: 'volcano' },
  ai_chat_trigger: { label: 'AI对话触发', color: 'purple' },
  external_link: { label: '外部链接', color: 'default' },
  photo_recognize_drug: { label: '拍照识药', color: 'cyan' },
  quick_ask: { label: '快捷提问', color: 'magenta' },
  health_self_check: { label: '健康自查', color: 'gold' },
  // 兼容旧值
  ai_dialog_trigger: { label: 'AI对话触发(旧)', color: 'purple' },
  drug_identify: { label: '拍照识药(旧)', color: 'cyan' },
};

const AI_FUNCTION_TYPE_LABEL: Record<string, string> = {
  // [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 新 5 项
  questionnaire: '对话内问卷',
  image_capture: '图像采集',
  file_upload: '文件上传',
  ai_dialog_trigger: 'AI 对话触发',
  quick_ask: '快捷提问',
  // 旧 4 项（运营仅在编辑老数据时短暂看到）
  photo_upload: '拍照上传(旧)',
  report_interpret: '报告解读(旧)',
  medicine_recognize: '拍照识药(旧)',
  health_self_check: '健康自查(旧)',
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
  // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 两个独立开关：是否推荐 / 是否胶囊
  is_recommended?: boolean;
  is_capsule?: boolean;
  // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 5 个新字段
  grid_sort?: number;
  capsule_sort?: number;
  ai_function_type?: string | null;
  ai_opening?: string | null;
  pre_card_for_navigate?: boolean | null;
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
  // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 4 个健康自查专用字段
  health_check_template_id?: number | null;
  archive_missing_strategy?: string | null;
  prompt_override_enabled?: boolean | null;
  prompt_override_text?: string | null;
  // [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 新 3 字段
  questionnaire_template_id?: number | null;
  capture_purpose?: string | null;
  pre_card_enabled?: boolean | null;
  trigger_by_keyword?: boolean | null;
  trigger_by_intent?: boolean | null;
  trigger_keywords?: string[] | null;
  ai_reference_passive?: boolean | null;
  ai_reference_active?: boolean | null;
  // [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 问卷展示形态
  questionnaire_display_form?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface QuestionnaireTemplateOption {
  id: number;
  code: string;
  name: string;
  status?: number;
}

interface HealthCheckTemplateOption {
  id: number;
  name: string;
  default_prompt: string;
  enabled: boolean;
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
  // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 视图类型：grid / capsule / all
  const [viewType, setViewType] = useState<'grid' | 'capsule' | 'all'>('grid');
  const [form] = Form.useForm();
  const watchedButtonType = Form.useWatch('button_type', form);
  const watchedName = Form.useWatch('name', form);
  const watchedIcon = Form.useWatch('icon', form);
  // [PRD-AICHAT-FUNCBTN-OPTIM-V1] 新增：监听 ai_function_type 与 pre_card_for_navigate 用于条件渲染
  const watchedAiFunctionType = Form.useWatch('ai_function_type', form);
  const watchedPreCardForNavigate = Form.useWatch('pre_card_for_navigate', form);
  const [promptOptions, setPromptOptions] = useState<PromptTemplateOption[]>([]);
  // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查问卷模板下拉数据
  const [healthCheckTemplates, setHealthCheckTemplates] = useState<HealthCheckTemplateOption[]>([]);
  const watchedHealthTplId = Form.useWatch('health_check_template_id', form);
  const watchedPromptOverride = Form.useWatch('prompt_override_enabled', form);
  // [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 通用问卷模板下拉数据
  const [questionnaireTemplates, setQuestionnaireTemplates] = useState<QuestionnaireTemplateOption[]>([]);
  const watchedQuestionnaireTplId = Form.useWatch('questionnaire_template_id', form);
  const watchedCapturePurpose = Form.useWatch('capture_purpose', form);
  const watchedPreCardEnabled = Form.useWatch('pre_card_enabled', form);
  // [AICHAT-OPTIM-FIX-V1 F-01] Emoji 选择器弹窗状态
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false);
  // [PRD-AICHAT-FUNCCARD-V2 2026-05-20] 卡片预览浮层（375x667 手机框 1:1 还原 H5 真机效果）
  const [previewOpen, setPreviewOpen] = useState(false);
  const watchedCardTitle = Form.useWatch('card_title', form);
  const watchedCardSubtitle = Form.useWatch('card_subtitle', form);
  const watchedCardCoverImage = Form.useWatch('card_cover_image', form);
  const watchedButtonSubDesc = Form.useWatch('button_sub_desc', form);
  const watchedPreCardIcon = Form.useWatch('pre_card_icon', form);
  const watchedPreCardIconType = Form.useWatch('pre_card_icon_type', form);

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

  // [PRD-HEALTH-SELF-CHECK-V1] 拉取健康自查问卷模板下拉
  const fetchHealthCheckTemplates = useCallback(async () => {
    try {
      const res = await get<any>('/api/admin/health-check-templates', { page: 1, page_size: 200 });
      const items = Array.isArray(res) ? res : (res?.items || []);
      setHealthCheckTemplates(
        items
          .filter((t: any) => t && t.id)
          .map((t: any) => ({
            id: t.id,
            name: t.name,
            default_prompt: t.default_prompt || '',
            enabled: t.enabled !== false,
          })),
      );
    } catch {
      setHealthCheckTemplates([]);
    }
  }, []);

  // [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 拉取通用问卷模板下拉
  const fetchQuestionnaireTemplates = useCallback(async () => {
    try {
      const res = await get<any>('/api/admin/questionnaire/templates', { page: 1, page_size: 200 });
      const items = Array.isArray(res) ? res : (res?.items || []);
      setQuestionnaireTemplates(
        items
          .filter((t: any) => t && t.id)
          .map((t: any) => ({
            id: t.id,
            code: t.code,
            name: t.name,
            status: t.status,
          })),
      );
    } catch {
      setQuestionnaireTemplates([]);
    }
  }, []);

  useEffect(() => {
    fetchPromptTemplates();
    fetchHealthCheckTemplates();
    fetchQuestionnaireTemplates();
  }, [fetchPromptTemplates, fetchHealthCheckTemplates, fetchQuestionnaireTemplates]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] view_type 参数：grid / capsule / all
      const params: Record<string, any> = { page, page_size: pageSize };
      if (viewType !== 'all') {
        params.view_type = viewType;
      }
      const res = await get<any>('/api/admin/function-buttons', params);
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
  }, [page, pageSize, viewType]);

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
        // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 两个独立开关回填（无值时按 false）
        is_recommended: !!record.is_recommended,
        is_capsule: !!record.is_capsule,
        // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 新字段回填
        ai_function_type: record.ai_function_type || undefined,
        ai_opening: record.ai_opening || '',
        pre_card_for_navigate: !!record.pre_card_for_navigate,
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
        // [PRD-HEALTH-SELF-CHECK-V1] 健康自查 4 字段回填
        health_check_template_id: record.health_check_template_id || undefined,
        archive_missing_strategy: record.archive_missing_strategy || 'use_default',
        prompt_override_enabled: !!record.prompt_override_enabled,
        prompt_override_text: record.prompt_override_text || '',
        // [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 3 字段回填
        questionnaire_template_id: record.questionnaire_template_id || undefined,
        capture_purpose: record.capture_purpose || undefined,
        // pre_card_enabled 兼容老字段 pre_card_for_navigate：优先用新字段，回退到旧字段，默认 true
        pre_card_enabled:
          record.pre_card_enabled !== null && record.pre_card_enabled !== undefined
            ? !!record.pre_card_enabled
            : !!record.pre_card_for_navigate || true,
        // [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 问卷展示形态回填
        questionnaire_display_form: record.questionnaire_display_form || 'DRAWER_SCROLL',
        // [PRD-QUESTIONNAIRE-DRAWER-V1.2 2026-05-20] 引导卡片图标三选一回填
        pre_card_icon: (record as any).pre_card_icon || '',
        pre_card_icon_type: (record as any).pre_card_icon_type || 'default',
        // [PRD-TCM-DRAWER-V12 2026-05-20] 触发开关 / AI 引用 回填（NULL 视为 true）
        trigger_by_keyword: (record as any).trigger_by_keyword !== false,
        trigger_by_intent: (record as any).trigger_by_intent !== false,
        trigger_keywords: Array.isArray((record as any).trigger_keywords) ? (record as any).trigger_keywords : [],
        ai_reference_passive: (record as any).ai_reference_passive !== false,
        ai_reference_active: (record as any).ai_reference_active !== false,
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
        // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 新增按钮的默认值：两个开关都强制 OFF
        is_recommended: false,
        is_capsule: false,
        sort_weight: 0,
        photo_tip_text: '请确保药品名称、品牌、规格完整，拍摄清晰',
        max_photo_count: 5,
        auto_user_message: '',
        card_title: '',
        icon: '📌',
        archive_missing_strategy: 'use_default',
        prompt_override_enabled: false,
        // [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 默认值
        pre_card_enabled: true,
        // [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 默认抽屉-一屏多题
        questionnaire_display_form: 'DRAWER_SCROLL',
        // [PRD-QUESTIONNAIRE-DRAWER-V1.2 2026-05-20] 引导卡片图标默认走默认 SVG
        pre_card_icon: '',
        pre_card_icon_type: 'default',
        // [PRD-TCM-DRAWER-V12 2026-05-20] 触发开关 / AI 引用 默认两个都开启
        trigger_by_keyword: true,
        trigger_by_intent: true,
        trigger_keywords: [],
        ai_reference_passive: true,
        ai_reference_active: true,
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
        // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 两个独立开关
        is_recommended: !!values.is_recommended,
        is_capsule: !!values.is_capsule,
        // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 5 个新字段
        ai_function_type: values.button_type === 'ai_function' ? (values.ai_function_type || null) : null,
        ai_opening: (values.ai_opening || '').trim() || null,
        pre_card_for_navigate: values.button_type === 'page_navigate' ? !!values.pre_card_for_navigate : false,
        params: finalParams,
        // [AI对话模式优化 PRD v1.0] 8 个新字段（按类型条件传）
        prompt_template_id: PROMPT_TEMPLATE_REQUIRED_TYPES.has(values.button_type)
          ? (values.prompt_template_id || null)
          : null,
        // [PRD-PAGE-NAVIGATE-EXTERNAL-URL-FIX-V1 2026-05-19] Bug 修复 F1：
        // page_navigate 主类型也允许写入 external_url（之前只认老枚举 external_link，
        // 导致新类型 page_navigate 在保存时被强制置 null，DB 中链接被擦除）
        external_url:
          values.button_type === 'page_navigate' || values.button_type === 'external_link'
            ? (values.external_url || null)
            : null,
        preset_prompt: values.button_type === 'quick_ask' ? (values.preset_prompt || null) : null,
        auto_user_message: values.auto_user_message || '',
        card_title: values.card_title || '',
        card_subtitle: values.card_subtitle || null,
        // [PRD-AICHAT-CAPSULE-V2 2026-05-15] 不再编辑「卡片封面图 URL」，前端永远传 null（后端兼容接收）
        card_cover_image: null,
        button_sub_desc: values.button_sub_desc || null,
        // [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查 4 字段（仅 health_self_check 类型生效）
        health_check_template_id: values.button_type === 'health_self_check'
          ? (values.health_check_template_id || null) : null,
        archive_missing_strategy: values.button_type === 'health_self_check'
          ? (values.archive_missing_strategy || 'use_default') : null,
        prompt_override_enabled: values.button_type === 'health_self_check'
          ? !!values.prompt_override_enabled : null,
        prompt_override_text: values.button_type === 'health_self_check' && values.prompt_override_enabled
          ? (values.prompt_override_text || null) : null,
        // [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 3 个新字段
        // - questionnaire_template_id：仅 ai_function_type=questionnaire 时生效
        // - capture_purpose：仅 ai_function_type=image_capture 时生效
        // - pre_card_enabled：对所有 ai_function 类按钮统一可用（默认 true）
        questionnaire_template_id:
          values.button_type === 'ai_function' && values.ai_function_type === 'questionnaire'
            ? (values.questionnaire_template_id || null)
            : null,
        capture_purpose:
          values.button_type === 'ai_function' && values.ai_function_type === 'image_capture'
            ? (values.capture_purpose || null)
            : null,
        // [PRD-PAGE-NAVIGATE-EXTERNAL-URL-FIX-V1 2026-05-19] Bug 修复 F2：pre_card_enabled 语义对齐
        //   - ai_function：保持原逻辑（默认 true）
        //   - page_navigate：对应 pre_card_for_navigate 开关
        //   - 其它老类型：默认 true，避免误判为关闭说明卡片
        pre_card_enabled:
          values.button_type === 'ai_function'
            ? (values.pre_card_enabled !== undefined ? !!values.pre_card_enabled : true)
            : values.button_type === 'page_navigate'
              ? !!values.pre_card_for_navigate
              : true,
        // [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 问卷展示形态
        questionnaire_display_form:
          values.button_type === 'ai_function' && values.ai_function_type === 'questionnaire'
            ? (values.questionnaire_display_form || 'DRAWER_SCROLL')
            : null,
        // [PRD-QUESTIONNAIRE-DRAWER-V1.2 2026-05-20] 引导卡片图标三选一
        // - ai_function 时才生效；其他类型置空
        // - icon_type=default 时强制把 icon 内容清空
        pre_card_icon_type:
          values.button_type === 'ai_function'
            ? (values.pre_card_icon_type || 'default')
            : null,
        pre_card_icon:
          values.button_type === 'ai_function' && (values.pre_card_icon_type === 'url' || values.pre_card_icon_type === 'emoji')
            ? (values.pre_card_icon || null)
            : null,
        // [PRD-TCM-DRAWER-V12 2026-05-20] 双触发开关 + AI 引用双开关 + 关键词列表
        // 仅 ai_function 类按钮才有意义；其它类型按 null 传，后端忽略
        trigger_by_keyword: values.button_type === 'ai_function'
          ? (values.trigger_by_keyword !== undefined ? !!values.trigger_by_keyword : true)
          : null,
        trigger_by_intent: values.button_type === 'ai_function'
          ? (values.trigger_by_intent !== undefined ? !!values.trigger_by_intent : true)
          : null,
        trigger_keywords: values.button_type === 'ai_function'
          ? (Array.isArray(values.trigger_keywords) ? values.trigger_keywords : null)
          : null,
        ai_reference_passive: values.button_type === 'ai_function'
          ? (values.ai_reference_passive !== undefined ? !!values.ai_reference_passive : true)
          : null,
        ai_reference_active: values.button_type === 'ai_function'
          ? (values.ai_reference_active !== undefined ? !!values.ai_reference_active : true)
          : null,
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

  // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 快速切换"是否推荐"——列表上点一下立即生效
  const handleToggleRecommended = async (record: FunctionButton, checked: boolean) => {
    // 乐观更新：先本地切，失败回滚
    setItems((prev) => prev.map((it) => (it.id === record.id ? { ...it, is_recommended: checked } : it)));
    try {
      await patch(`/api/admin/function-buttons/${record.id}/toggle-recommended`, { value: checked });
      message.success(checked ? '已开启（5 分钟内全端生效）' : '已关闭（5 分钟内全端生效）');
    } catch {
      setItems((prev) => prev.map((it) => (it.id === record.id ? { ...it, is_recommended: !checked } : it)));
      message.error('切换失败');
    }
  };

  // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 快速切换"是否胶囊"——列表上点一下立即生效
  const handleToggleCapsule = async (record: FunctionButton, checked: boolean) => {
    setItems((prev) => prev.map((it) => (it.id === record.id ? { ...it, is_capsule: checked } : it)));
    try {
      await patch(`/api/admin/function-buttons/${record.id}/toggle-capsule`, { value: checked });
      message.success(checked ? '已开启（5 分钟内全端生效）' : '已关闭（5 分钟内全端生效）');
    } catch {
      setItems((prev) => prev.map((it) => (it.id === record.id ? { ...it, is_capsule: !checked } : it)));
      message.error('切换失败');
    }
  };

  // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 单按钮原子排序操作：置顶 / 上移 / 下移
  const handleSortAction = async (record: FunctionButton, action: 'top' | 'up' | 'down') => {
    if (viewType === 'all') {
      message.warning('请先切换到"宫格视图"或"胶囊视图"再调整排序');
      return;
    }
    try {
      await post('/api/admin/function-buttons/sort-action', {
        id: record.id,
        view_type: viewType,
        action,
      });
      message.success(action === 'top' ? '已置顶' : action === 'up' ? '已上移' : '已下移');
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '排序失败');
    }
  };

  const columns = [
    // [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 排序值列：根据当前 viewType 显示对应排序值
    {
      title: viewType === 'capsule' ? '胶囊排序' : viewType === 'grid' ? '宫格排序' : '排序权重',
      dataIndex: viewType === 'capsule' ? 'capsule_sort' : viewType === 'grid' ? 'grid_sort' : 'sort_weight',
      key: 'sort_value',
      width: 90,
      render: (val: any, record: FunctionButton) => {
        if (viewType === 'capsule') return record.capsule_sort ?? '-';
        if (viewType === 'grid') return record.grid_sort ?? '-';
        return record.sort_weight ?? '-';
      },
    },
    {
      title: '图标',
      // [AICHAT-OPTIM-FIX-V1 F-01] 图标列改为显示 Emoji 字符（24px 字号）
      dataIndex: 'icon',
      key: 'icon',
      width: 70,
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
      width: 130,
    },
    {
      title: '按钮类型',
      dataIndex: 'button_type',
      key: 'button_type',
      width: 130,
      render: (val: string, record: FunctionButton) => {
        const info = BUTTON_TYPE_MAP[val];
        const main = info ? <Tag color={info.color}>{info.label}</Tag> : <Tag>{val}</Tag>;
        // ai_function 显示子类型小标签
        if (val === 'ai_function' && record.ai_function_type) {
          const sub = AI_FUNCTION_TYPE_LABEL[record.ai_function_type] || record.ai_function_type;
          return (
            <Space size={4} wrap>
              {main}
              <Tag color="blue">{sub}</Tag>
            </Space>
          );
        }
        return main;
      },
    },
    // [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 删除"启用状态"列，替换为"是否推荐"+"是否胶囊"两列
    {
      title: '是否推荐',
      dataIndex: 'is_recommended',
      key: 'is_recommended',
      width: 110,
      render: (val: boolean, record: FunctionButton) => (
        <Switch
          checked={!!val}
          checkedChildren="开"
          unCheckedChildren="关"
          onChange={(checked) => handleToggleRecommended(record, checked)}
        />
      ),
    },
    {
      title: '是否胶囊',
      dataIndex: 'is_capsule',
      key: 'is_capsule',
      width: 110,
      render: (val: boolean, record: FunctionButton) => (
        <Switch
          checked={!!val}
          checkedChildren="开"
          unCheckedChildren="关"
          onChange={(checked) => handleToggleCapsule(record, checked)}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 280,
      render: (_: any, record: FunctionButton, index: number) => (
        <Space size={4} wrap>
          {/* [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 排序按钮：仅在 grid/capsule 视图显示 */}
          {viewType !== 'all' && (
            <>
              <Button
                type="link"
                size="small"
                icon={<VerticalAlignTopOutlined />}
                onClick={() => handleSortAction(record, 'top')}
                title="置顶"
              >
                置顶
              </Button>
              <Button
                type="link"
                size="small"
                icon={<ArrowUpOutlined />}
                disabled={index === 0}
                onClick={() => handleSortAction(record, 'up')}
                title="上移"
              />
              <Button
                type="link"
                size="small"
                icon={<ArrowDownOutlined />}
                disabled={index === items.length - 1}
                onClick={() => handleSortAction(record, 'down')}
                title="下移"
              />
            </>
          )}
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
      <Title level={4} style={{ marginBottom: 16 }}>功能按钮管理</Title>
      {/* [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] Tab 视图切换：宫格 / 胶囊 / 全部 */}
      <Tabs
        activeKey={viewType}
        onChange={(k) => {
          setViewType(k as 'grid' | 'capsule' | 'all');
          setPage(1);
        }}
        items={[
          { key: 'grid', label: '宫格视图（按 grid_sort 升序）' },
          { key: 'capsule', label: '胶囊视图（按 capsule_sort 升序）' },
          { key: 'all', label: '全部按钮' },
        ]}
      />
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
        title={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: 24 }}>
            <span>{editingItem ? '编辑功能按钮' : '新增功能按钮'}</span>
            {/* [PRD-AICHAT-FUNCCARD-V2 2026-05-20] 卡片预览入口 */}
            <Button
              type="primary"
              ghost
              size="small"
              icon={<EyeOutlined />}
              onClick={() => setPreviewOpen(true)}
              data-testid="function-card-preview-trigger"
            >
              预览效果
            </Button>
          </div>
        }
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
            extra="新建按钮请优先选「页面跳转」或「AI 功能」两大类；下方括号「兼容」标记的为老类型，仅供回看老数据。"
          >
            <Select placeholder="请选择按钮类型" options={BUTTON_TYPE_OPTIONS} />
          </Form.Item>

          {/* [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] AI 功能子类型 */}
          {watchedButtonType === 'ai_function' && (
            <Form.Item
              label="AI 功能子类型"
              name="ai_function_type"
              rules={[{ required: true, message: '请选择 AI 功能子类型' }]}
              extra="新版只剩 5 个永久稳定子类型；选择「对话内问卷」后由问卷模板区分业务，选择「图像采集」后由用途区分识药/上传/报告解读。"
            >
              <Select placeholder="请选择 AI 功能子类型" options={AI_FUNCTION_TYPE_OPTIONS} />
            </Form.Item>
          )}

          {/* [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] questionnaire 子类型：关联问卷模板 */}
          {watchedButtonType === 'ai_function' && watchedAiFunctionType === 'questionnaire' && (
            <>
              <Form.Item
                label="关联问卷模板"
                name="questionnaire_template_id"
                rules={[{ required: true, message: '请选择问卷模板' }]}
                extra={
                  <span>
                    问卷模板由「问卷模板管理」页面维护；
                    <a onClick={() => router.push('/questionnaire-templates')}>前往问卷模板管理</a>
                  </span>
                }
              >
                <Select
                  placeholder="请选择问卷模板"
                  showSearch
                  optionFilterProp="label"
                  options={questionnaireTemplates.map((t) => ({
                    value: t.id,
                    label: `${t.name}（${t.code}）`,
                  }))}
                />
              </Form.Item>
              {/* [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 问卷展示形态：三选一 */}
              <Form.Item
                label="问卷展示形态"
                name="questionnaire_display_form"
                initialValue="DRAWER_SCROLL"
                rules={[{ required: true, message: '请选择问卷展示形态' }]}
                extra={
                  <span>
                    决定用户点击按钮后问卷以何种形态出现：
                    <b>抽屉-一屏多题</b>（健康自查推荐）/ <b>抽屉-一题一屏</b>（沉浸式体质测评）/ <b>对话内插入</b>（轻量级）
                  </span>
                }
              >
                <Select
                  placeholder="请选择问卷展示形态"
                  options={QUESTIONNAIRE_DISPLAY_FORM_OPTIONS}
                />
              </Form.Item>
            </>
          )}

          {/* [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] image_capture 子类型：采集用途 */}
          {watchedButtonType === 'ai_function' && watchedAiFunctionType === 'image_capture' && (
            <Form.Item
              label="采集用途"
              name="capture_purpose"
              rules={[{ required: true, message: '请选择采集用途' }]}
              extra="不同用途决定卡片上展示的按钮：识药/上传 = 相册+拍照；报告解读 = 相册+拍照+历史报告"
            >
              <Select placeholder="请选择采集用途" options={CAPTURE_PURPOSE_OPTIONS} />
            </Form.Item>
          )}

          {/* [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19] 说明卡片开关：对所有 ai_function 按钮统一可用 */}
          {watchedButtonType === 'ai_function' && (
            <Form.Item
              label="对话内说明卡片"
              name="pre_card_enabled"
              valuePropName="checked"
              extra="开启后，用户点击按钮先在对话区插入一张说明卡片（方案 D · 宾尼天蓝），用户点卡片「开始」按钮再真正进抽屉。关闭则直接进入功能流程，无卡片铺垫。"
            >
              <Switch checkedChildren="开（默认）" unCheckedChildren="关" />
            </Form.Item>
          )}

          {/* [PRD-TCM-DRAWER-V12 2026-05-20] AI 功能按钮 - 双触发开关 + AI 引用双开关 + 关键词列表 */}
          {watchedButtonType === 'ai_function' && (
            <div
              style={{
                border: '1px solid #E0E7FF',
                borderRadius: 8,
                padding: '12px 14px',
                marginBottom: 16,
                background: '#F8FAFF',
              }}
              data-testid="fn-btn-tcm-trigger-block"
            >
              <div style={{ fontWeight: 600, marginBottom: 10, color: '#1F2937' }}>
                聊天触发与 AI 引用（默认全部开启）
              </div>
              <Form.Item
                label="启用关键词触发"
                name="trigger_by_keyword"
                valuePropName="checked"
                extra="开启后，用户在聊天输入命中关键词时，自动弹出说明卡片，引导用户进入本功能"
              >
                <Switch checkedChildren="开（默认）" unCheckedChildren="关" />
              </Form.Item>
              <Form.Item
                label="启用 AI 意图识别触发"
                name="trigger_by_intent"
                valuePropName="checked"
                extra="关键词未命中时，再用 AI 意图识别兜底，仍命中则弹出说明卡片"
              >
                <Switch checkedChildren="开（默认）" unCheckedChildren="关" />
              </Form.Item>
              <Form.Item
                label="触发关键词列表"
                name="trigger_keywords"
                extra="输入后回车，命中任一关键词即触发。默认体质测评关键词；其它按钮可自定义"
              >
                <Select
                  mode="tags"
                  placeholder="输入关键词后回车，可添加多个"
                  tokenSeparators={[',', '，']}
                  style={{ width: '100%' }}
                />
              </Form.Item>
              <Form.Item
                label="AI 对话被动引用本功能结果"
                name="ai_reference_passive"
                valuePropName="checked"
                extra="开启后，AI 在回答健康相关问题时，会把用户最近一次本功能的结果作为上下文"
              >
                <Switch checkedChildren="开（默认）" unCheckedChildren="关" />
              </Form.Item>
              <Form.Item
                label="完成后 AI 主动追问"
                name="ai_reference_active"
                valuePropName="checked"
                extra="开启后，用户完成本功能后，AI 在对话流中主动追加一条引导追问"
              >
                <Switch checkedChildren="开（默认）" unCheckedChildren="关" />
              </Form.Item>
            </div>
          )}

          {/* [PRD-QUESTIONNAIRE-DRAWER-V1.2 2026-05-20] 引导卡片图标三选一 */}
          {watchedButtonType === 'ai_function' && watchedPreCardEnabled !== false && (
            <>
              <Form.Item
                label="卡片图标"
                name="pre_card_icon_type"
                extra="三选一：上传图片 / 选择 Emoji / 使用默认。默认走系统问卷 SVG"
              >
                <Select
                  options={[
                    { label: '使用默认（系统问卷 SVG）', value: 'default' },
                    { label: '选择 Emoji', value: 'emoji' },
                    { label: '上传图片 URL', value: 'url' },
                  ]}
                />
              </Form.Item>
              <Form.Item
                noStyle
                shouldUpdate={(prev, next) => prev.pre_card_icon_type !== next.pre_card_icon_type}
              >
                {({ getFieldValue }) => {
                  const t = getFieldValue('pre_card_icon_type');
                  if (t === 'emoji') {
                    return (
                      <Form.Item
                        label="选择 Emoji"
                        name="pre_card_icon"
                        extra="常用：🩺 🧬 💊 🥗 😴 🚶 📋 🌿 🍎 ⏰ 📝 ❤️"
                      >
                        <Input placeholder="🩺" maxLength={8} style={{ width: 120, fontSize: 22 }} />
                      </Form.Item>
                    );
                  }
                  if (t === 'url') {
                    return (
                      <Form.Item
                        label="图标 URL"
                        name="pre_card_icon"
                        rules={[
                          {
                            validator: (_, v) => {
                              if (!v) return Promise.resolve();
                              const s = String(v).trim();
                              if (s.startsWith('http://') || s.startsWith('https://') || s.startsWith('/')) {
                                return Promise.resolve();
                              }
                              return Promise.reject(new Error('URL 必须以 http(s):// 或 / 开头'));
                            },
                          },
                        ]}
                      >
                        <Input placeholder="https://example.com/icon.png" />
                      </Form.Item>
                    );
                  }
                  return null;
                }}
              </Form.Item>
            </>
          )}

          {/* [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 页面跳转：地址 + 先弹卡片再跳转开关 */}
          {watchedButtonType === 'page_navigate' && (
            <>
              <Form.Item
                label="跳转地址"
                name="external_url"
                rules={[
                  { required: true, message: '请输入跳转地址' },
                  {
                    validator: (_, v) => {
                      if (!v) return Promise.resolve();
                      const s = String(v).trim();
                      if (s.startsWith('http://') || s.startsWith('https://') || s.startsWith('/') || s.startsWith('pages/')) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error('地址必须以 http(s):// 或 / 或 pages/ 开头'));
                    },
                  },
                ]}
                extra="http(s):// 开头视为外部链接；/ 或 pages/ 开头视为内部页面"
              >
                <Input placeholder="例：https://example.com  或  /services  或  pages/index/index" />
              </Form.Item>
              <Form.Item
                label="先弹卡片再跳转"
                name="pre_card_for_navigate"
                valuePropName="checked"
                extra="开启后，点击按钮先在对话区弹出引导卡片，用户点卡片按钮再跳转。常用于风险提示 / 二次确认。"
              >
                <Switch checkedChildren="开" unCheckedChildren="关" />
              </Form.Item>
            </>
          )}
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
          {/* [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查类型专属 3 项配置 */}
          {watchedButtonType === 'health_self_check' && (
            <>
              <Form.Item
                label="关联问卷模板"
                name="health_check_template_id"
                rules={[{ required: true, message: '请选择关联问卷模板' }]}
                extra="数据源：AI 咨询配置 → 健康自查问卷模板"
              >
                <Select
                  placeholder="请选择问卷模板"
                  options={healthCheckTemplates
                    .filter((t) => t.enabled)
                    .map((t) => ({ value: t.id, label: t.name }))}
                  showSearch
                  allowClear
                  filterOption={(input, option) =>
                    String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                  }
                  notFoundContent={
                    <div style={{ padding: 12, textAlign: 'center' }}>
                      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可用问卷模板" />
                      <Button type="link" size="small" onClick={() => router.push('/health-check-templates')}>
                        去问卷模板配置 →
                      </Button>
                    </div>
                  }
                />
              </Form.Item>
              <Form.Item
                label="未选档案时的行为"
                name="archive_missing_strategy"
                rules={[{ required: true, message: '请选择未选档案策略' }]}
              >
                <Select options={ARCHIVE_MISSING_STRATEGY_OPTIONS} />
              </Form.Item>
              <Form.Item
                label="Prompt 配置"
                name="prompt_override_enabled"
                valuePropName="checked"
                extra="开启后将使用按钮自定义 Prompt 覆盖模板默认值"
              >
                <Switch checkedChildren="自定义" unCheckedChildren="继承默认" />
              </Form.Item>
              {watchedPromptOverride && (
                <Form.Item
                  label="自定义 Prompt 全文"
                  name="prompt_override_text"
                  rules={[{ required: true, message: '请输入自定义 Prompt' }]}
                  extra={
                    <span style={{ fontSize: 12, color: '#888' }}>
                      支持占位符：{'{档案信息} {部位} {症状列表} {持续时间} {档案年龄} {档案性别} {档案既往病史} {档案过敏史}'}
                      <Button
                        type="link"
                        size="small"
                        style={{ padding: '0 4px' }}
                        onClick={() => {
                          const tpl = healthCheckTemplates.find((t) => t.id === watchedHealthTplId);
                          if (tpl?.default_prompt) {
                            form.setFieldsValue({ prompt_override_text: tpl.default_prompt });
                            message.success('已填入模板默认 Prompt 内容');
                          } else {
                            message.warning('请先选择关联问卷模板');
                          }
                        }}
                      >
                        填入模板默认 Prompt
                      </Button>
                    </span>
                  }
                >
                  <TextArea rows={8} placeholder="请输入自定义 Prompt 全文" />
                </Form.Item>
              )}
            </>
          )}
          {/* 通用 8 字段：所有类型可填 */}
          <Form.Item
            label="自动用户消息"
            name="auto_user_message"
            rules={[{
              required: watchedButtonType !== 'health_self_check',
              message: '请输入点击后插入对话流的用户消息',
            }]}
            extra="点击按钮后插入对话流的用户气泡文案，例：我想做体质测评（健康自查类型可留空）"
          >
            <Input placeholder="例：我想做体质测评" maxLength={200} />
          </Form.Item>
          <Form.Item
            label="卡片标题"
            name="card_title"
            rules={[{
              required: watchedButtonType !== 'health_self_check',
              message: '请输入卡片标题',
            }]}
          >
            <Input placeholder="卡片头部主标题（健康自查类型可留空）" maxLength={50} />
          </Form.Item>
          {/* [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] AI 开场白：可留空 */}
          {(watchedButtonType === 'ai_function' ||
            (watchedButtonType === 'page_navigate' && watchedPreCardForNavigate)) && (
            <Form.Item
              label="AI 开场白"
              name="ai_opening"
              extra="可留空。非空时点击按钮后 AI 先冒一句话，再弹出操作卡片。例：好的，我们一起来识别一下您手上的药品~"
            >
              <TextArea rows={2} placeholder="留空则跳过开场白直接弹卡片" maxLength={300} showCount />
            </Form.Item>
          )}
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
          {/* [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 用两个独立开关替代原"启用状态"字段 */}
          <Form.Item
            label="是否推荐"
            name="is_recommended"
            valuePropName="checked"
            extra="开启后，本按钮将出现在 AI 对话首页的功能宫格中"
          >
            <Switch checkedChildren="开" unCheckedChildren="关" />
          </Form.Item>
          <Form.Item
            label="是否胶囊"
            name="is_capsule"
            valuePropName="checked"
            extra="开启后，本按钮将出现在 AI 对话输入框上方的胶囊条中"
          >
            <Switch checkedChildren="开" unCheckedChildren="关" />
          </Form.Item>
          {/* 保留 is_enabled 隐藏字段以兼容旧后端写入（业务侧已停止读取，过渡期不删） */}
          <Form.Item name="is_enabled" hidden>
            <Switch />
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

      {/* [PRD-AICHAT-FUNCCARD-V2 2026-05-20] 卡片预览浮层
          - 375x667 手机框 1:1 还原 H5 真机效果
          - 表单字段（主标题/副标题/封面图/按钮副说明/图标）实时联动
          - 关闭：点击遮罩或 ✕ */}
      <Modal
        title="卡片预览（375 × 667 手机真机效果）"
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={null}
        width={460}
        destroyOnClose
        styles={{ body: { padding: '20px 24px 24px', background: '#F1F5F9' } }}
        data-testid="function-card-preview-modal"
      >
        <div data-testid="function-card-preview-modal-body">
          <PhonePreviewFrame>
            <FunctionCardV2Preview
              data={{
                title: watchedCardTitle || watchedName || '功能引导',
                subtitle: watchedCardSubtitle || null,
                coverImage: watchedCardCoverImage || null,
                icon:
                  watchedPreCardIconType === 'emoji'
                    ? watchedPreCardIcon || watchedIcon || null
                    : watchedPreCardIconType === 'url'
                    ? watchedPreCardIcon || null
                    : watchedIcon || null,
                iconType: watchedPreCardIconType || (watchedIcon ? 'emoji' : 'default'),
                buttonSubDesc: watchedButtonSubDesc || null,
                buttonText: '立即查看',
              }}
            />
          </PhonePreviewFrame>
          <div style={{ marginTop: 12, color: '#64748B', fontSize: 12, textAlign: 'center' }}>
            预览实时联动表单字段修改，无需保存即可查看效果
          </div>
        </div>
      </Modal>
    </div>
  );
}
