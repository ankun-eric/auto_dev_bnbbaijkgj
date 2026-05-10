'use client';

/**
 * [PRD-432 2026-05-09] AI 回答顶部「咨询对象档案」折叠卡片
 *
 * 每条 AI 回答上方都挂一张独立的"档案折叠卡片"：
 * - 折叠态：单行（44pt）— 头像/性别图标 + "本次回答结合 XX 的档案" + 灰字摘要 + 箭头
 * - 展开态：完整 7 项字段 + 完整度提示 + "档案已于 MM/DD 更新"
 * - 长期用药字段唯一可点击 → 弹出半屏抽屉（MedicationDrawer）
 *
 * 数据来源：GET /api/v1/consultant/{id}/profile_card
 */

import { useEffect, useState } from 'react';
import api from '@/lib/api';
import MedicationDrawer from './MedicationDrawer';
import AdvisorCapsule from './AdvisorCapsule';

export interface ProfileCardProps {
  consultantId: number;
  /** 当 consultantId 不可用时（未选对象/兜底）显示的引导卡片 */
  fallbackText?: string;
  onFallbackClick?: () => void;
  /** 跳转到当前咨询对象的「档案完善页」，默认为 /health-archive?target=<id> */
  onGoComplete?: (consultantId: number) => void;
  /** 跳转到「用药管理设置页」 */
  onGoMedicationManage?: (consultantId: number, autoCreate: boolean) => void;
  /**
   * [PRD-448] 展示模式
   * - 'legacy'（默认）：保留原 PRD-432 折叠卡片样式（外部胶囊 + 灰色摘要）
   * - 'capsule'：使用新「咨询人胶囊」（AdvisorCapsule）作为折叠态，
   *   折叠态浅灰圆角胶囊 + 小人图标 + "XXX 的档案" + 箭头；展开态保留 7 项档案字段。
   *   用于 AI 首页 / AI 对话详情页气泡内部第一行。
   */
  variant?: 'legacy' | 'capsule';
}

interface ProfileField<T> {
  value: T;
  filled: boolean;
  is_none?: boolean;
}

interface ProfileCardData {
  consultant_id: number;
  nickname: string;
  avatar_url: string;
  is_self: boolean;
  fields: {
    gender: ProfileField<string>;
    age: ProfileField<number | null>;
    height: ProfileField<string>;
    weight: ProfileField<string>;
    past_history: ProfileField<string[]>;
    allergy: ProfileField<string[]>;
    long_term_meds: ProfileField<string> & { count: number; value_brief?: string };
  };
  completeness: {
    filled_count: number;
    total: number;
    percent: number;
  };
  summary_text: string;
  last_updated_at: string | null;
  updated_within_30d: boolean;
}

function formatMonthDay(iso: string | null): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${m}/${dd}`;
  } catch {
    return '';
  }
}

function genderIcon(gender: string): string {
  if (gender === '男' || gender === 'male') return '♂';
  if (gender === '女' || gender === 'female') return '♀';
  return '👤';
}

function genderColor(gender: string): string {
  if (gender === '男' || gender === 'male') return '#3B82F6';
  if (gender === '女' || gender === 'female') return '#EC4899';
  return '#9CA3AF';
}

const _profileCardCache: Record<number, { data: ProfileCardData; ts: number }> = {};
const CACHE_TTL = 30 * 1000;

export function clearProfileCardCache(consultantId?: number) {
  if (consultantId === undefined) {
    Object.keys(_profileCardCache).forEach((k) => delete _profileCardCache[Number(k)]);
  } else {
    delete _profileCardCache[consultantId];
  }
}

export default function ProfileCard({
  consultantId,
  fallbackText,
  onFallbackClick,
  onGoComplete,
  onGoMedicationManage,
  variant = 'legacy',
}: ProfileCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [data, setData] = useState<ProfileCardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!consultantId && consultantId !== 0) return;
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    const cached = _profileCardCache[consultantId];
    if (cached && Date.now() - cached.ts < CACHE_TTL) {
      setData(cached.data);
      return;
    }
    setLoading(true);
    setError(false);

    // [Bug-432-fix 2026-05-09]
    // 修因：axios 响应拦截器已在 lib/api.ts 内执行 `(response) => response.data`，
    // 这里 then 中的 `res` 实际就是后端 JSON 响应体本身（含 nickname/fields/...），
    // 之前再写 `res.data` 等于二次脱壳，结果是 undefined → setData(undefined) → loading 永不解除。
    // 修复：直接把 `res` 当作 payload 使用；类型守卫确保结构合法。
    const fetchOnce = (): Promise<ProfileCardData> => {
      return api
        .get(`/api/v1/consultant/${consultantId}/profile_card`)
        .then((res) => {
          // 拦截器已脱壳，res 本身就是 JSON 体
          const payload = res as unknown as ProfileCardData;
          if (!payload || typeof payload !== 'object' || !('fields' in payload)) {
            throw new Error('invalid profile_card payload');
          }
          return payload;
        });
    };

    const apply = (payload: ProfileCardData) => {
      _profileCardCache[consultantId] = { data: payload, ts: Date.now() };
      if (!cancelled) {
        setData(payload);
        setError(false);
        setLoading(false);
      }
    };

    fetchOnce()
      .then(apply)
      .catch(() => {
        // PRD 3.10：失败保留 1 次自动重试，3s 后再请求一次
        if (cancelled) return;
        retryTimer = setTimeout(() => {
          if (cancelled) return;
          fetchOnce()
            .then(apply)
            .catch(() => {
              if (cancelled) return;
              setError(true);
              setLoading(false);
            });
        }, 3000);
      });

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [consultantId]);

  if (fallbackText) {
    if (variant === 'capsule') {
      // [PRD-448 v1.1 §3.3] 未选定 / 名字为空 → 整条胶囊不渲染（不再显示占位胶囊）
      return null;
    }
    return (
      <div
        data-testid="ai-profile-card-fallback"
        onClick={onFallbackClick}
        style={{
          margin: '8px 12px 4px',
          padding: '10px 12px',
          borderRadius: 8,
          background: '#EAF4FF',
          color: '#2563EB',
          fontSize: 13,
          cursor: 'pointer',
        }}
      >
        {fallbackText} →
      </div>
    );
  }

  if (error || !data) {
    if (variant === 'capsule') {
      // [PRD-448 v1.1 §3.3] 加载中 / 失败 / 名字为空 → 整条胶囊不渲染
      // 不再显示"加载中…"或"我的档案"占位（避免半成品胶囊或文案抖动）
      return null;
    }
    if (error)
      return null;
    return (
      <div
        data-testid="ai-profile-card-loading"
        style={{
          margin: '8px 12px 4px',
          padding: '10px 12px',
          borderRadius: 8,
          background: '#F4F6FA',
          color: '#9CA3AF',
          fontSize: 12,
        }}
      >
        加载档案中...
      </div>
    );
  }

  const f = data.fields;
  const summary = data.summary_text || '';

  const meds = f.long_term_meds;
  const medsClickable = !meds.is_none;

  const completePercent = data.completeness.percent;
  const isComplete = completePercent >= 100;

  // [PRD-448] 7 项档案字段公共渲染（详情页/AI 首页通用，作为 AdvisorCapsule 展开内容）
  const sevenFieldsContent = (
    <div
      data-testid="ai-profile-card-expanded"
      data-consultant-id={data.consultant_id}
      style={{
        background: '#F4F6FA',
        borderRadius: 8,
        padding: '8px 12px 10px',
        fontSize: 13,
        color: '#374151',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          padding: '4px 0 8px',
          fontSize: 12,
        }}
      >
        <div
          data-testid="ai-profile-card-completeness"
          style={{
            color: isComplete ? '#10B981' : '#2563EB',
            cursor: isComplete ? 'default' : 'pointer',
          }}
          onClick={() => {
            if (!isComplete) onGoComplete?.(data.consultant_id);
          }}
        >
          {isComplete ? '档案已完整 ✓' : `档案完整度 ${completePercent}%，点击补全 ›`}
        </div>
        {data.updated_within_30d && data.last_updated_at && (
          <div style={{ color: '#9CA3AF' }}>
            档案已于 {formatMonthDay(data.last_updated_at)} 更新
          </div>
        )}
      </div>
      <Row label="性别" value={renderField(f.gender, 'string')} />
      <Row label="年龄" value={f.age.filled ? `${f.age.value} 岁` : <Empty />} />
      <Row label="身高" value={renderField(f.height, 'string')} />
      <Row label="体重" value={renderField(f.weight, 'string')} />
      <Row label="既往病史" value={renderListField(f.past_history)} />
      <Row label="过敏史" value={renderListField(f.allergy)} />
      <Row
        label="长期用药"
        clickable={medsClickable}
        onClick={() => {
          if (medsClickable) setDrawerOpen(true);
        }}
        value={
          meds.is_none ? (
            <span style={{ color: '#9CA3AF' }}>无</span>
          ) : meds.count > 0 ? (
            <span>
              {meds.value_brief || `共 ${meds.count} 项`}
              <span style={{ marginLeft: 4, color: '#9CA3AF' }}>›</span>
            </span>
          ) : (
            <span style={{ color: '#9CA3AF' }}>
              未填写 <span style={{ marginLeft: 4 }}>›</span>
            </span>
          )
        }
      />
    </div>
  );

  if (variant === 'capsule') {
    // [PRD-448 v1.1 §4.2] 本人固定显示「本人」，不显示真实姓名/账号昵称（避免隐私泄露）
    // 非本人：显示成员真实 name；name 为空时由 AdvisorCapsule 内部 §3.3 兜底（不渲染）
    const displayName = data.is_self ? '本人' : (data.nickname || '');
    return (
      <div data-testid="ai-profile-card" data-consultant-id={data.consultant_id}>
        <AdvisorCapsule
          memberName={displayName}
          isSelf={data.is_self}
          expanded={expanded}
          onToggle={(next) => setExpanded(next)}
          expandedContent={sevenFieldsContent}
          testId="ai-advisor-capsule"
        />
        {drawerOpen && (
          <MedicationDrawer
            consultantId={data.consultant_id}
            consultantName={data.nickname}
            onClose={() => setDrawerOpen(false)}
            onGoManage={() => {
              setDrawerOpen(false);
              onGoMedicationManage?.(data.consultant_id, false);
            }}
            onGoCreate={() => {
              setDrawerOpen(false);
              onGoMedicationManage?.(data.consultant_id, true);
            }}
          />
        )}
      </div>
    );
  }

  return (
    <div
      data-testid="ai-profile-card"
      data-consultant-id={data.consultant_id}
      style={{
        margin: '8px 12px 4px',
        background: '#F4F6FA',
        borderRadius: 8,
        overflow: 'hidden',
        fontSize: 13,
        color: '#374151',
      }}
    >
      <div
        data-testid="ai-profile-card-collapsed"
        onClick={() => setExpanded((v) => !v)}
        style={{
          height: 44,
          display: 'flex',
          alignItems: 'center',
          padding: '0 12px',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <div
          style={{
            width: 24,
            height: 24,
            borderRadius: '50%',
            background: genderColor(f.gender.value),
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 14,
            marginRight: 8,
            flexShrink: 0,
          }}
        >
          {genderIcon(f.gender.value)}
        </div>
        <div
          style={{
            flex: 1,
            overflow: 'hidden',
            whiteSpace: 'nowrap',
            textOverflow: 'ellipsis',
            fontWeight: 500,
            color: '#1F2937',
          }}
        >
          本次回答结合 {data.nickname || '本人'} 的档案
        </div>
        {summary && (
          <div
            style={{
              color: '#6B7280',
              marginLeft: 8,
              fontSize: 12,
              maxWidth: '50%',
              overflow: 'hidden',
              whiteSpace: 'nowrap',
              textOverflow: 'ellipsis',
            }}
          >
            {summary}
          </div>
        )}
        <div style={{ marginLeft: 8, color: '#9CA3AF', fontSize: 12 }}>
          {expanded ? '▴' : '▾'}
        </div>
      </div>

      {expanded && (
        <div data-testid="ai-profile-card-expanded" style={{ padding: '0 12px 10px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: '8px 0',
              borderTop: '1px solid #E5E7EB',
              fontSize: 12,
            }}
          >
            <div
              data-testid="ai-profile-card-completeness"
              style={{ color: isComplete ? '#10B981' : '#2563EB', cursor: isComplete ? 'default' : 'pointer' }}
              onClick={() => {
                if (!isComplete) onGoComplete?.(data.consultant_id);
              }}
            >
              {isComplete
                ? '档案已完整 ✓'
                : `档案完整度 ${completePercent}%，点击补全 ›`}
            </div>
            {data.updated_within_30d && data.last_updated_at && (
              <div style={{ color: '#9CA3AF' }}>
                档案已于 {formatMonthDay(data.last_updated_at)} 更新
              </div>
            )}
          </div>

          <Row label="性别" value={renderField(f.gender, 'string')} />
          <Row label="年龄" value={f.age.filled ? `${f.age.value} 岁` : <Empty />} />
          <Row label="身高" value={renderField(f.height, 'string')} />
          <Row label="体重" value={renderField(f.weight, 'string')} />
          <Row label="既往病史" value={renderListField(f.past_history)} />
          <Row label="过敏史" value={renderListField(f.allergy)} />
          <Row
            label="长期用药"
            clickable={medsClickable}
            onClick={() => {
              if (medsClickable) setDrawerOpen(true);
            }}
            value={
              meds.is_none ? (
                <span style={{ color: '#9CA3AF' }}>无</span>
              ) : meds.count > 0 ? (
                <span>
                  {meds.value_brief || `共 ${meds.count} 项`}
                  <span style={{ marginLeft: 4, color: '#9CA3AF' }}>›</span>
                </span>
              ) : (
                <span style={{ color: '#9CA3AF' }}>
                  未填写 <span style={{ marginLeft: 4 }}>›</span>
                </span>
              )
            }
          />
        </div>
      )}

      {drawerOpen && (
        <MedicationDrawer
          consultantId={data.consultant_id}
          consultantName={data.nickname}
          onClose={() => setDrawerOpen(false)}
          onGoManage={() => {
            setDrawerOpen(false);
            onGoMedicationManage?.(data.consultant_id, false);
          }}
          onGoCreate={() => {
            setDrawerOpen(false);
            onGoMedicationManage?.(data.consultant_id, true);
          }}
        />
      )}
    </div>
  );
}

function Row({
  label,
  value,
  clickable,
  onClick,
}: {
  label: string;
  value: React.ReactNode;
  clickable?: boolean;
  onClick?: () => void;
}) {
  return (
    <div
      data-testid={`ai-profile-card-row-${label}`}
      onClick={onClick}
      style={{
        display: 'flex',
        padding: '6px 0',
        cursor: clickable ? 'pointer' : 'default',
        background: clickable ? '#FAFCFF' : 'transparent',
        borderRadius: 4,
      }}
    >
      <div style={{ width: 80, color: '#6B7280', fontSize: 13 }}>{label}</div>
      <div
        style={{
          flex: 1,
          color: '#111827',
          fontSize: 13,
          maxWidth: '65%',
          overflow: 'hidden',
          whiteSpace: 'nowrap',
          textOverflow: 'ellipsis',
        }}
      >
        {value}
      </div>
    </div>
  );
}

function Empty() {
  return <span style={{ color: '#9CA3AF' }}>未填写</span>;
}

function renderField(field: ProfileField<string>, _t: 'string'): React.ReactNode {
  if (!field.filled || !field.value) return <Empty />;
  return field.value;
}

function renderListField(field: ProfileField<string[]>): React.ReactNode {
  if (field.is_none) return <span style={{ color: '#9CA3AF' }}>无</span>;
  if (!field.filled || !field.value || field.value.length === 0) return <Empty />;
  const list = field.value;
  if (list.length === 1) return list[0];
  const total = list.length;
  return `${list.slice(0, 2).join('、')} 等 ${total} 项`;
}
