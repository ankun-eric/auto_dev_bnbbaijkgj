'use client';

/**
 * [PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] 家庭守护列表（主账号视角）
 *
 * 列出当前主账号已守护的所有家人 + 本人对自己的提醒配置入口。
 * 每一项点击进入被守护人详情页（含 AI 外呼提醒设置 + TA 的设备只读视图 + 解除守护）。
 */

export const dynamic = 'force-dynamic';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { BH_TOKENS } from '@/lib/health-tokens';

interface AiCallItem {
  target_user_id: number;
  target_nickname: string | null;
  is_self: boolean;
  enabled: boolean;
  dnd_start: string;
  dnd_end: string;
  call_target: string;
  has_guardian: boolean;
}

function FamilyGuardianListInner() {
  const router = useRouter();
  const sp = useSearchParams();
  const reminderTarget = sp?.get('reminder') || null; // 'self' / target=<id>
  const initialTarget = sp?.get('target');
  const [items, setItems] = useState<AiCallItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTarget, setActiveTarget] = useState<number | null>(
    initialTarget ? Number(initialTarget) : null
  );

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/health-archive/ai-call/settings');
      const data = res.data || res;
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch {
      setItems([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  useEffect(() => {
    if (reminderTarget === 'self' && items.length > 0) {
      const self = items.find((it) => it.is_self);
      if (self) setActiveTarget(self.target_user_id);
    }
  }, [reminderTarget, items]);

  const handleEntryClick = (it: AiCallItem) => {
    if (it.is_self) {
      setActiveTarget(it.target_user_id);
    } else {
      router.push(`/family-guardian-list/${it.target_user_id}`);
    }
  };

  return (
    <div style={{ background: BH_TOKENS.bgPage, minHeight: '100vh', paddingBottom: 80 }}>
      <GreenNavBar>家庭守护列表</GreenNavBar>
      <div style={{ padding: '12px 16px' }}>
        <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 12 }}>
          {loading ? '加载中…' : `已守护 ${items.filter((it) => !it.is_self).length} 人 + 本人对自己`}
        </div>

        {items.map((it) => (
          <div
            key={it.target_user_id}
            data-testid={`bh-guardian-item-${it.target_user_id}`}
            onClick={() => handleEntryClick(it)}
            style={{
              background: '#fff', borderRadius: 12, padding: 14, marginBottom: 12,
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 12,
            }}
          >
            <div
              style={{
                width: 44, height: 44, borderRadius: '50%',
                background: it.is_self ? '#A7F3D0' : '#BAE6FD',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 22,
              }}
            >{it.is_self ? '🙂' : '👤'}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 600, color: '#1f2937' }}>
                {it.target_nickname || `用户#${it.target_user_id}`}
                {it.is_self && (
                  <span style={{ fontSize: 11, color: '#0EA5E9', marginLeft: 6 }}>（本人）</span>
                )}
              </div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                AI 外呼：{it.enabled ? `开 · 免打扰 ${it.dnd_start}-${it.dnd_end}` : '关'}
              </div>
            </div>
            <span style={{ fontSize: 20, color: '#9ca3af' }}>›</span>
          </div>
        ))}

        {!loading && items.length === 0 && (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#9ca3af', fontSize: 13 }}>
            暂无守护关系。可在「健康档案」中选中家人发起邀请共管。
          </div>
        )}

        {/* 本人的提醒配置（就地展开） */}
        {activeTarget != null && (
          <SettingsPanel
            targetId={activeTarget}
            onClose={() => setActiveTarget(null)}
            onSaved={() => { fetchItems(); }}
          />
        )}
      </div>
    </div>
  );
}

function SettingsPanel({
  targetId, onClose, onSaved,
}: {
  targetId: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [setting, setSetting] = useState<AiCallItem | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res: any = await api.get(`/api/health-archive/ai-call/settings/${targetId}`);
        setSetting(res.data || res);
      } catch {}
    })();
  }, [targetId]);

  const update = async (patch: Partial<AiCallItem>) => {
    try {
      const res: any = await api.put(`/api/health-archive/ai-call/settings/${targetId}`, patch);
      setSetting(res.data || res);
      Toast.show({ content: '已保存', icon: 'success', duration: 800 });
      onSaved();
    } catch {
      Toast.show({ content: '保存失败', icon: 'fail' });
    }
  };

  if (!setting) return null;

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
        zIndex: 100, display: 'flex', alignItems: 'flex-end',
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff', width: '100%',
          borderTopLeftRadius: 16, borderTopRightRadius: 16,
          padding: 16, maxHeight: '85vh', overflowY: 'auto',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ fontSize: 17, fontWeight: 700 }}>
            AI 外呼提醒设置（{setting.target_nickname || `用户#${setting.target_user_id}`}）
          </span>
          <span onClick={onClose} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
        </div>

        {/* 总开关 */}
        <div
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 0', borderBottom: '1px solid #f3f4f6',
          }}
        >
          <span style={{ fontSize: 14 }}>AI 外呼总开关</span>
          <label style={{ position: 'relative', display: 'inline-block', width: 44, height: 24 }}>
            <input
              type="checkbox"
              data-testid="bh-aicall-enabled-toggle"
              checked={setting.enabled}
              onChange={(e) => update({ enabled: e.target.checked })}
              style={{ opacity: 0, width: 0, height: 0 }}
            />
            <span
              style={{
                position: 'absolute', cursor: 'pointer',
                top: 0, left: 0, right: 0, bottom: 0,
                background: setting.enabled ? '#0EA5E9' : '#d1d5db',
                borderRadius: 24, transition: '0.2s',
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  height: 18, width: 18, left: setting.enabled ? 22 : 4, bottom: 3,
                  background: '#fff', borderRadius: '50%', transition: '0.2s',
                }}
              />
            </span>
          </label>
        </div>

        {/* 免打扰时段 */}
        <div style={{ padding: '12px 0', borderBottom: '1px solid #f3f4f6' }}>
          <div style={{ fontSize: 14, marginBottom: 8 }}>免打扰时段</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="time"
              data-testid="bh-aicall-dnd-start"
              value={setting.dnd_start}
              onChange={(e) => update({ dnd_start: e.target.value })}
              style={{ padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 6 }}
            />
            <span style={{ color: '#9ca3af' }}>~</span>
            <input
              type="time"
              data-testid="bh-aicall-dnd-end"
              value={setting.dnd_end}
              onChange={(e) => update({ dnd_end: e.target.value })}
              style={{ padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 6 }}
            />
          </div>
          <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 6 }}>
            该时段内不外呼（默认建议 22:00-07:00，跨天有效）
          </div>
        </div>

        {/* 外呼对象 */}
        <div style={{ padding: '12px 0' }}>
          <div style={{ fontSize: 14, marginBottom: 8 }}>外呼对象</div>
          <div style={{ display: 'flex', gap: 8 }}>
            {[
              { value: 'self', label: '被守护人本人' },
              { value: 'guardian', label: '守护者', disabled: !setting.has_guardian },
            ].map((opt) => {
              const active = setting.call_target === opt.value;
              return (
                <button
                  key={opt.value}
                  data-testid={`bh-aicall-target-${opt.value}`}
                  disabled={opt.disabled}
                  onClick={() => update({ call_target: opt.value })}
                  style={{
                    flex: 1, padding: '8px 0', borderRadius: 8,
                    background: active ? '#0EA5E9' : (opt.disabled ? '#f3f4f6' : '#fff'),
                    color: active ? '#fff' : (opt.disabled ? '#9ca3af' : '#374151'),
                    border: active ? 'none' : '1px solid #d1d5db',
                    fontSize: 13, fontWeight: 600,
                    cursor: opt.disabled ? 'not-allowed' : 'pointer',
                  }}
                >{opt.label}</button>
              );
            })}
          </div>
          {!setting.has_guardian && (
            <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 6 }}>
              本人无守护者，"外呼对象=守护者"选项不可用；如选择会自动回退为"被守护人本人"。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function FamilyGuardianListPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>加载中…</div>}>
      <FamilyGuardianListInner />
    </Suspense>
  );
}
