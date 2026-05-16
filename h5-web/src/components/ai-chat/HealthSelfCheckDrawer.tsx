'use client';

/**
 * [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查抽屉
 *
 * 底部上拉抽屉，三步问卷：选部位 → 选症状 → 选持续时间
 * 顶部档案信息只读展示，提交后调用 /api/health-self-check/start
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import api from '@/lib/api';
import { formatGender } from '@/utils/format';

export interface BodyPartItem {
  id: number;
  name: string;
  icon: string;
  symptoms: string[];
  sort_order: number;
  enabled: boolean;
}

export interface HealthCheckTemplateDetail {
  id: number;
  name: string;
  description?: string;
  duration_options: string[];
  default_prompt: string;
  enabled: boolean;
  body_parts_detail: BodyPartItem[];
}

export interface HealthSelfCheckSubmitPayload {
  template_id: number;
  button_id: number;
  archive_id?: number | null;
  archive_name?: string;
  archive_age?: number | null;
  archive_gender?: string | null;
  body_part: { id: number; name: string; icon: string };
  symptoms: string[];
  duration: string;
  // [PRD-HSC-SSE 2026-05-16] 步骤 2.5 补充症状描述（选填，硬上限 50 字）
  symptom_description?: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  /** 当前按钮配置（决定模板 ID、按钮 ID） */
  button: {
    id: number;
    name?: string;
    health_check_template_id?: number | null;
    archive_missing_strategy?: string | null;
    prompt_override_enabled?: boolean | null;
    prompt_override_text?: string | null;
  } | null;
  /** 当前选定档案 */
  archive: {
    id?: number | null;
    name?: string;
    age?: number | null;
    gender?: string | null;
    isDefault?: boolean;
  } | null;
  /** 提交回调：抽屉关闭后，由外部将卡片插入对话流 + 调用后端 start 接口 */
  onSubmit: (payload: HealthSelfCheckSubmitPayload, template: HealthCheckTemplateDetail) => void;
  /** 预填数据（重新自查） */
  prefill?: Partial<HealthSelfCheckSubmitPayload> | null;
}

export default function HealthSelfCheckDrawer({
  open,
  onClose,
  button,
  archive,
  onSubmit,
  prefill,
}: Props) {
  const [template, setTemplate] = useState<HealthCheckTemplateDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedPartId, setSelectedPartId] = useState<number | null>(null);
  const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
  const [selectedDuration, setSelectedDuration] = useState<string>('');
  // [PRD-HSC-SSE 2026-05-16] 步骤 2.5：补充症状描述（选填，硬上限 50 字）
  const [symptomDescription, setSymptomDescription] = useState<string>('');
  const [highlightMissing, setHighlightMissing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2200);
  };

  // 加载模板
  useEffect(() => {
    if (!open || !button?.health_check_template_id) return;
    let cancelled = false;
    setLoading(true);
    setErrorMsg(null);
    api
      .get<any>(`/api/health-self-check/template/${button.health_check_template_id}`)
      .then((res: any) => {
        if (cancelled) return;
        const data: HealthCheckTemplateDetail = res?.data ?? res;
        if (!data || !data.enabled) {
          setErrorMsg('该功能暂不可用，请联系管理员');
          setTemplate(null);
          return;
        }
        setTemplate(data);
      })
      .catch(() => {
        if (!cancelled) setErrorMsg('模板加载失败，请稍后重试');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, button?.health_check_template_id]);

  // 预填
  useEffect(() => {
    if (!open) {
      setSelectedPartId(null);
      setSelectedSymptoms([]);
      setSelectedDuration('');
      setSymptomDescription('');
      setHighlightMissing(false);
      return;
    }
    if (prefill?.body_part?.id) setSelectedPartId(prefill.body_part.id);
    if (prefill?.symptoms) setSelectedSymptoms(prefill.symptoms);
    if (prefill?.duration) setSelectedDuration(prefill.duration);
    if (prefill?.symptom_description) {
      setSymptomDescription(String(prefill.symptom_description).slice(0, 50));
    } else {
      setSymptomDescription('');
    }
  }, [open, prefill]);

  const selectedPart: BodyPartItem | null = useMemo(() => {
    if (!template || selectedPartId == null) return null;
    return template.body_parts_detail.find((p) => p.id === selectedPartId) || null;
  }, [template, selectedPartId]);

  const toggleSymptom = (sym: string) => {
    setSelectedSymptoms((prev) =>
      prev.includes(sym) ? prev.filter((s) => s !== sym) : prev.concat(sym),
    );
  };

  const handleSubmit = useCallback(() => {
    if (!template || !button) return;
    if (!selectedPartId || selectedSymptoms.length === 0 || !selectedDuration) {
      setHighlightMissing(true);
      showToast('请完成全部三项后再开始分析');
      return;
    }
    const part = template.body_parts_detail.find((p) => p.id === selectedPartId);
    if (!part) return;
    // 未选档案且策略为 prompt_on_submit
    if (!archive?.id && button.archive_missing_strategy === 'prompt_on_submit') {
      showToast('请先在顶部选择咨询档案');
      return;
    }
    onSubmit(
      {
        template_id: template.id,
        button_id: Number(button.id),
        archive_id: archive?.id ?? null,
        archive_name: archive?.name,
        archive_age: archive?.age ?? null,
        archive_gender: archive?.gender ?? null,
        body_part: { id: part.id, name: part.name, icon: part.icon },
        symptoms: selectedSymptoms,
        duration: selectedDuration,
        symptom_description: symptomDescription,
      },
      template,
    );
  }, [template, button, archive, selectedPartId, selectedSymptoms, selectedDuration, symptomDescription, onSubmit]);

  if (!open) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1500,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 480,
          height: '85vh',
          background: '#fff',
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 顶部标题 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '14px 16px',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          <div style={{ fontSize: 16, fontWeight: 600 }}>🩺 健康自查</div>
          <div
            style={{ fontSize: 14, color: '#999', cursor: 'pointer', padding: '4px 8px' }}
            onClick={onClose}
          >
            × 关闭
          </div>
        </div>

        {/* 档案只读 */}
        <div style={{ padding: '10px 16px', background: '#f7f8fa', fontSize: 13, color: '#555' }}>
          咨询档案：
          {archive?.name ? (
            <span style={{ color: '#222', fontWeight: 500 }}>
              {archive.name}
              {archive.age != null ? `（${archive.age}岁` : ''}
              {archive.gender ? `·${formatGender(archive.gender)}` : ''}
              {archive.age != null ? '）' : ''}
            </span>
          ) : (
            <span style={{ color: '#bbb' }}>未选择</span>
          )}
          {archive?.isDefault && (
            <span
              style={{
                marginLeft: 8,
                padding: '1px 6px',
                background: '#e6f4ff',
                color: '#1677ff',
                borderRadius: 4,
                fontSize: 11,
              }}
            >
              默认档案
            </span>
          )}
          <div style={{ marginTop: 4, fontSize: 11, color: '#999' }}>
            如需切换档案，请关闭后在顶部切换
          </div>
        </div>

        {/* 主体内容 */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {loading && <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>加载中…</div>}
          {!loading && errorMsg && (
            <div style={{ textAlign: 'center', color: '#ff4d4f', padding: 40 }}>{errorMsg}</div>
          )}
          {!loading && !errorMsg && template && (
            <>
              {/* 步骤 1：部位 */}
              <div style={{ marginBottom: 18 }}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    marginBottom: 8,
                    color: highlightMissing && !selectedPartId ? '#ff4d4f' : '#222',
                  }}
                >
                  步骤 1：选择部位
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, 1fr)',
                    gap: 8,
                  }}
                >
                  {template.body_parts_detail.map((p) => {
                    const active = selectedPartId === p.id;
                    return (
                      <div
                        key={p.id}
                        onClick={() => {
                          setSelectedPartId(p.id);
                          setSelectedSymptoms([]);
                        }}
                        style={{
                          textAlign: 'center',
                          padding: '12px 6px',
                          border: active ? '2px solid #1677ff' : '1px solid #e8e8e8',
                          borderRadius: 8,
                          background: active ? '#e6f4ff' : '#fafafa',
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{ fontSize: 22, lineHeight: 1, marginBottom: 4 }}>
                          {p.icon || '🧩'}
                        </div>
                        <div style={{ fontSize: 12, color: active ? '#1677ff' : '#333' }}>
                          {p.name}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 步骤 2：症状 */}
              <div style={{ marginBottom: 18 }}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    marginBottom: 8,
                    color:
                      highlightMissing && selectedSymptoms.length === 0 ? '#ff4d4f' : '#222',
                  }}
                >
                  步骤 2：选择症状（多选）
                </div>
                {!selectedPart && (
                  <div style={{ fontSize: 12, color: '#999' }}>请先选择上方的部位</div>
                )}
                {selectedPart && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {selectedPart.symptoms.map((s) => {
                      const active = selectedSymptoms.includes(s);
                      return (
                        <div
                          key={s}
                          onClick={() => toggleSymptom(s)}
                          style={{
                            padding: '6px 12px',
                            borderRadius: 16,
                            border: active ? '1px solid #1677ff' : '1px solid #e8e8e8',
                            background: active ? '#1677ff' : '#fff',
                            color: active ? '#fff' : '#333',
                            fontSize: 13,
                            cursor: 'pointer',
                          }}
                        >
                          {s}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* 步骤 2.5：补充症状描述（选填，硬上限 50 字） */}
              <div style={{ marginBottom: 18 }}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    marginBottom: 8,
                    color: '#222',
                  }}
                >
                  步骤 2.5：补充症状描述（选填）
                </div>
                <div style={{ position: 'relative' }}>
                  <input
                    type="text"
                    value={symptomDescription}
                    maxLength={50}
                    onChange={(e) => setSymptomDescription(e.target.value.slice(0, 50))}
                    placeholder="请详细描述您的症状..."
                    style={{
                      width: '100%',
                      padding: '10px 56px 10px 12px',
                      fontSize: 13,
                      border: '1px solid #e8e8e8',
                      borderRadius: 8,
                      background: '#fff',
                      color: '#333',
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      right: 10,
                      bottom: 6,
                      fontSize: 11,
                      color: '#bbb',
                      pointerEvents: 'none',
                    }}
                  >
                    {symptomDescription.length}/50
                  </div>
                </div>
              </div>

              {/* 步骤 3：持续时间 */}
              <div style={{ marginBottom: 18 }}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    marginBottom: 8,
                    color: highlightMissing && !selectedDuration ? '#ff4d4f' : '#222',
                  }}
                >
                  步骤 3：选择持续时间
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {template.duration_options.map((d) => {
                    const active = selectedDuration === d;
                    return (
                      <div
                        key={d}
                        onClick={() => setSelectedDuration(d)}
                        style={{
                          padding: '6px 14px',
                          borderRadius: 16,
                          border: active ? '1px solid #1677ff' : '1px solid #e8e8e8',
                          background: active ? '#e6f4ff' : '#fff',
                          color: active ? '#1677ff' : '#333',
                          fontSize: 13,
                          cursor: 'pointer',
                        }}
                      >
                        {d}
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>

        {/* 底部按钮 */}
        <div style={{ padding: 12, borderTop: '1px solid #f0f0f0' }}>
          <button
            onClick={handleSubmit}
            disabled={loading || !template || !!errorMsg}
            style={{
              width: '100%',
              padding: 12,
              background: loading || !template ? '#bfbfbf' : '#1677ff',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontSize: 15,
              fontWeight: 600,
              cursor: loading || !template ? 'not-allowed' : 'pointer',
            }}
          >
            开始 AI 分析
          </button>
        </div>

        {/* Toast */}
        {toast && (
          <div
            style={{
              position: 'absolute',
              bottom: 80,
              left: '50%',
              transform: 'translateX(-50%)',
              background: 'rgba(0,0,0,0.75)',
              color: '#fff',
              fontSize: 13,
              padding: '8px 14px',
              borderRadius: 6,
            }}
          >
            {toast}
          </div>
        )}
      </div>
    </div>
  );
}
