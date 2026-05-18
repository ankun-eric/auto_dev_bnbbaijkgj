'use client';
/**
 * [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 查看用药计划抽屉
 *
 * 在 AI 对话页识药卡片下方点击"查看用药计划"打开此抽屉。
 * 沿用 /ai-home/medication-plans 列表的展示效果，列表项支持：
 *   - 点击主体：抽屉内就地折叠/展开全部明细字段
 *   - 编辑：抽屉内复用 MedicationFormPanel
 *   - 删除：二次确认 → 调删除接口 → 移除 + Toast
 *   - 空态：「该咨询人暂无用药计划」+ 「去新增」按钮
 *
 * 全程不跳路由、不开新页面，所有操作均在抽屉内完成。
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Toast, Dialog } from 'antd-mobile';
import api from '@/lib/api';
import MedicationFormPanel from '@/components/medication/MedicationFormPanel';

interface PlanItem {
  id: number;
  medicine_name: string;
  drug_name?: string;
  dosage?: string;
  dosage_value?: string | null;
  dosage_unit?: string | null;
  frequency?: string;
  frequency_per_day?: number | null;
  custom_times?: string[] | null;
  schedule?: string[];
  start_date?: string | null;
  end_date?: string | null;
  long_term?: boolean;
  guidance?: string | null;
  notes?: string | null;
  status?: string;
  generic_name?: string | null;
  family_member_id?: number | null;
  disease_tags?: string[] | null;
  is_ongoing?: boolean;
}

export interface ViewMedicationPlansDrawerProps {
  open: boolean;
  /** 当前 AI 对话页选中咨询人 family_member.id；本人态传 null/0 */
  familyMemberId?: number | null;
  /** 咨询人昵称（用于抽屉标题）；本人态传空 */
  consultantName?: string | null;
  /** 是否本人态 */
  isSelf?: boolean;
  onClose: () => void;
  /** 点击「去新增」时回调（关闭本抽屉 + 打开加入抽屉） */
  onGoAdd?: () => void;
  /** 列表中任意条目变更后回调（识药卡片需重刷状态） */
  onChanged?: () => void;
}

const PRIMARY = '#0EA5E9';
const TEXT = '#1F2937';
const SUB = '#6B7280';

export default function ViewMedicationPlansDrawer({
  open,
  familyMemberId,
  consultantName,
  isSelf,
  onClose,
  onGoAdd,
  onChanged,
}: ViewMedicationPlansDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<PlanItem[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);

  const title = isSelf || !consultantName
    ? '我的用药计划'
    : `${consultantName} 的用药计划`;

  const consultantParam = familyMemberId && familyMemberId > 0
    ? familyMemberId
    : 0; // 0 = 本人

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get(
        `/api/health-plan/medications/list?tab=in_progress&consultant_id=${consultantParam}`,
      );
      const body = res.data || res;
      setItems(Array.isArray(body.items) ? body.items : []);
    } catch {
      Toast.show({ content: '加载失败', icon: 'fail' });
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [consultantParam]);

  useEffect(() => {
    if (open) {
      setExpandedId(null);
      setEditingId(null);
      loadItems();
    }
  }, [open, loadItems]);

  if (!open) return null;

  const handleDelete = async (it: PlanItem) => {
    const ok = await Dialog.confirm({ content: '确定删除该用药计划？' });
    if (!ok) return;
    try {
      await api.delete(`/api/health-plan/medications/${it.id}`);
      Toast.show({ content: '已删除', icon: 'success' });
      setItems((prev) => prev.filter((x) => x.id !== it.id));
      onChanged?.();
    } catch {
      Toast.show({ content: '删除失败', icon: 'fail' });
    }
  };

  const renderRange = (it: PlanItem) => {
    const s = it.start_date || '—';
    if (it.long_term) return `${s} 至 长期`;
    const e = it.end_date || '—';
    return `${s} 至 ${e}`;
  };

  const renderFreq = (it: PlanItem) => {
    const n = it.frequency_per_day || (it.schedule?.length ?? 1);
    const times = (it.custom_times && it.custom_times.length ? it.custom_times : it.schedule) || [];
    return `每日 ${n} 次${times.length ? ' · ' + times.join(' / ') : ''}`;
  };

  const renderDosage = (it: PlanItem) => {
    if (it.dosage_value && it.dosage_unit) return `${it.dosage_value} ${it.dosage_unit}`;
    return it.dosage || '—';
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        zIndex: 9998,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
      }}
      data-testid="view-medication-plans-drawer"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#F4F6F9',
          width: '100%',
          maxWidth: 600,
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            padding: '14px 16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid #F0F0F0',
            background: '#fff',
            borderTopLeftRadius: 16,
            borderTopRightRadius: 16,
            flexShrink: 0,
          }}
        >
          <div style={{ fontSize: 17, fontWeight: 700, color: TEXT }} data-testid="view-med-drawer-title">
            {title}
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: 'none', background: 'transparent', fontSize: 22, cursor: 'pointer', color: SUB }}
            aria-label="close"
            data-testid="view-med-drawer-close"
          >
            ✕
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px 20px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', color: SUB, padding: 40 }}>加载中…</div>
          ) : items.length === 0 ? (
            <div
              data-testid="view-med-empty"
              style={{
                background: '#fff',
                padding: '40px 20px',
                borderRadius: 12,
                textAlign: 'center',
                color: SUB,
              }}
            >
              <div style={{ fontSize: 48, marginBottom: 12 }}>💊</div>
              <div style={{ fontSize: 15, marginBottom: 16 }}>
                {isSelf ? '您' : (consultantName || '该咨询人')}暂无用药计划
              </div>
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onGoAdd?.();
                }}
                data-testid="view-med-empty-go-add"
                style={{
                  padding: '10px 28px',
                  background: PRIMARY,
                  color: '#fff',
                  border: 'none',
                  borderRadius: 20,
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                去新增
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {items.map((it) => {
                const expanded = expandedId === it.id;
                const isEditing = editingId === it.id;
                if (isEditing) {
                  return (
                    <div
                      key={it.id}
                      data-testid={`view-med-item-${it.id}-editing`}
                      style={{ background: '#fff', borderRadius: 12, overflow: 'hidden' }}
                    >
                      <MedicationFormPanel
                        key={`edit-${it.id}`}
                        planId={it.id}
                        mode="drawer"
                        familyMemberId={familyMemberId ?? null}
                        hideDelete
                        onSaved={() => {
                          setEditingId(null);
                          loadItems();
                          onChanged?.();
                        }}
                        onCancel={() => setEditingId(null)}
                      />
                    </div>
                  );
                }
                return (
                  <div
                    key={it.id}
                    data-testid={`view-med-item-${it.id}`}
                    style={{
                      background: '#fff',
                      padding: 14,
                      borderRadius: 12,
                      boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                    }}
                  >
                    <div
                      onClick={() => setExpandedId(expanded ? null : it.id)}
                      style={{ cursor: 'pointer' }}
                      data-testid={`view-med-item-${it.id}-toggle`}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 16, fontWeight: 700, color: TEXT }}>
                          💊 {it.medicine_name || it.drug_name}
                        </span>
                        <span style={{ fontSize: 12, color: PRIMARY }}>
                          {expanded ? '收起 ▲' : '展开 ▼'}
                        </span>
                      </div>
                      <div style={{ fontSize: 13, color: SUB, marginTop: 6 }}>
                        {renderDosage(it)} · {renderFreq(it)}
                      </div>
                      <div style={{ fontSize: 12, color: SUB, marginTop: 4 }}>
                        {renderRange(it)}
                        {it.guidance ? ` · ${it.guidance}` : ''}
                      </div>
                    </div>

                    {expanded && (
                      <div
                        data-testid={`view-med-item-${it.id}-detail`}
                        style={{
                          marginTop: 10,
                          padding: '10px 0 0',
                          borderTop: '1px dashed #E5E7EB',
                        }}
                      >
                        <DetailRow label="药品名称" value={it.medicine_name || it.drug_name} />
                        {it.generic_name && <DetailRow label="通用名" value={it.generic_name} />}
                        <DetailRow label="每次剂量" value={renderDosage(it)} />
                        <DetailRow label="用药频次" value={renderFreq(it)} />
                        <DetailRow label="服用周期" value={renderRange(it)} />
                        {it.guidance && <DetailRow label="服用时机" value={it.guidance} />}
                        {it.notes && <DetailRow label="备注" value={it.notes} />}
                        {it.disease_tags && it.disease_tags.length > 0 && (
                          <DetailRow label="关联疾病" value={it.disease_tags.join('、')} />
                        )}

                        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                          <button
                            type="button"
                            onClick={() => setEditingId(it.id)}
                            data-testid={`view-med-item-${it.id}-edit`}
                            style={{
                              flex: 1,
                              padding: '8px 0',
                              background: '#fff',
                              color: PRIMARY,
                              border: `1px solid ${PRIMARY}`,
                              borderRadius: 18,
                              fontSize: 13,
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            编辑
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(it)}
                            data-testid={`view-med-item-${it.id}-delete`}
                            style={{
                              flex: 1,
                              padding: '8px 0',
                              background: '#fff',
                              color: '#DC2626',
                              border: '1px solid #FCA5A5',
                              borderRadius: 18,
                              fontSize: 13,
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: any }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div style={{ display: 'flex', gap: 12, fontSize: 13, lineHeight: 1.8 }}>
      <span style={{ color: SUB, minWidth: 64, flexShrink: 0 }}>{label}</span>
      <span style={{ color: TEXT, wordBreak: 'break-word' }}>{String(value)}</span>
    </div>
  );
}
