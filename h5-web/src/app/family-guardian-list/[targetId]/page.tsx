'use client';

/**
 * [PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18 F5-3 F7 F9-3] 被守护人详情页
 *
 * - 模块 1：AI 外呼提醒设置（总开关 / 免打扰时段 / 外呼对象）
 * - 模块 2：TA 的设备（只读列表 + 提醒 TA 绑定）
 * - 模块 3：解除守护（底部，二次确认）
 */

export const dynamic = 'force-dynamic';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Dialog, Toast } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { BH_TOKENS } from '@/lib/health-tokens';
import { UNBIND_GUARDIAN_CONFIRM } from '@/lib/family-relation';

interface AiCallSetting {
  target_user_id: number;
  target_nickname: string | null;
  is_self: boolean;
  enabled: boolean;
  dnd_start: string;
  dnd_end: string;
  call_target: string;
  has_guardian: boolean;
}

interface DeviceItem {
  id: number;
  device_type: string;
  device_name?: string;
  status: string;
  last_sync_at?: string | null;
  bound_at?: string | null;
}

export default function GuardianTargetDetailPage() {
  const params = useParams<{ targetId: string }>();
  const router = useRouter();
  const targetId = Number(params?.targetId);

  const [setting, setSetting] = useState<AiCallSetting | null>(null);
  const [devices, setDevices] = useState<DeviceItem[]>([]);
  const [deviceLoading, setDeviceLoading] = useState(true);
  const [managementId, setManagementId] = useState<number | null>(null);

  const fetchSetting = useCallback(async () => {
    try {
      const res: any = await api.get(`/api/health-archive/ai-call/settings/${targetId}`);
      setSetting(res.data || res);
    } catch {
      setSetting(null);
    }
  }, [targetId]);

  const fetchDevices = useCallback(async () => {
    setDeviceLoading(true);
    try {
      const res: any = await api.get(`/api/health-archive/guardian/${targetId}/devices`);
      const data = res.data || res;
      setDevices(Array.isArray(data.items) ? data.items : []);
    } catch {
      setDevices([]);
    }
    setDeviceLoading(false);
  }, [targetId]);

  const fetchManagementId = useCallback(async () => {
    try {
      const res: any = await api.get('/api/family/management');
      const data = res.data || res;
      const items = Array.isArray(data.items) ? data.items : [];
      const m = items.find((it: any) => it.managed_user_id === targetId && it.status === 'active');
      setManagementId(m ? m.id : null);
    } catch {
      setManagementId(null);
    }
  }, [targetId]);

  useEffect(() => {
    if (!Number.isFinite(targetId) || targetId <= 0) return;
    fetchSetting();
    fetchDevices();
    fetchManagementId();
  }, [targetId, fetchSetting, fetchDevices, fetchManagementId]);

  const updateSetting = async (patch: Partial<AiCallSetting>) => {
    try {
      const res: any = await api.put(`/api/health-archive/ai-call/settings/${targetId}`, patch);
      setSetting(res.data || res);
      Toast.show({ content: '已保存', icon: 'success', duration: 800 });
    } catch {
      showToast('保存失败', 'fail');
    }
  };

  const remindBind = async () => {
    try {
      await api.post(`/api/health-archive/guardian/${targetId}/devices/remind-bind`);
      showToast('已提醒 TA 绑定设备');
    } catch {
      showToast('操作失败，请稍后再试', 'fail');
    }
  };

  const cancelManagement = async () => {
    if (managementId == null) {
      showToast('未找到守护关系', 'fail');
      return;
    }
    // [PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 使用统一二次确认文案
    const result = await Dialog.confirm({
      title: UNBIND_GUARDIAN_CONFIRM.title,
      content: UNBIND_GUARDIAN_CONFIRM.content,
      cancelText: UNBIND_GUARDIAN_CONFIRM.cancelText,
      confirmText: UNBIND_GUARDIAN_CONFIRM.confirmText,
    });
    if (!result) return;
    try {
      await api.delete(`/api/family/management/${managementId}`);
      showToast('已解除守护');
      setTimeout(() => router.back(), 800);
    } catch {
      showToast('操作失败，请稍后再试', 'fail');
    }
  };

  if (!setting) {
    return (
      <div style={{ background: BH_TOKENS.bgPage, minHeight: '100vh' }}>
        <GreenNavBar>守护详情</GreenNavBar>
        <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>加载中…</div>
      </div>
    );
  }

  return (
    <div style={{ background: BH_TOKENS.bgPage, minHeight: '100vh', paddingBottom: 80 }}>
      <GreenNavBar>{setting.target_nickname || `用户#${targetId}`} · 守护详情</GreenNavBar>

      <div style={{ padding: '12px 16px' }}>
        {/* 模块 1：AI 外呼提醒 */}
        <div
          style={{
            background: '#fff', borderRadius: 12, padding: 16, marginBottom: 12,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            borderLeft: '3px solid #0EA5E9',
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>📞 AI 外呼提醒</div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f3f4f6' }}>
            <span style={{ fontSize: 14 }}>AI 外呼总开关</span>
            <input
              type="checkbox"
              data-testid="bh-detail-aicall-enabled"
              checked={setting.enabled}
              onChange={(e) => updateSetting({ enabled: e.target.checked })}
              style={{ width: 20, height: 20 }}
            />
          </div>

          <div style={{ padding: '10px 0', borderBottom: '1px solid #f3f4f6' }}>
            <div style={{ fontSize: 14, marginBottom: 8 }}>免打扰时段</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="time"
                data-testid="bh-detail-dnd-start"
                value={setting.dnd_start}
                onChange={(e) => updateSetting({ dnd_start: e.target.value })}
                style={{ padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 6 }}
              />
              <span style={{ color: '#9ca3af' }}>~</span>
              <input
                type="time"
                data-testid="bh-detail-dnd-end"
                value={setting.dnd_end}
                onChange={(e) => updateSetting({ dnd_end: e.target.value })}
                style={{ padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: 6 }}
              />
            </div>
            <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 6 }}>
              该时段内不外呼（跨天有效，默认 22:00-07:00）
            </div>
          </div>

          <div style={{ padding: '10px 0' }}>
            <div style={{ fontSize: 14, marginBottom: 8 }}>外呼对象</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {[
                { value: 'self', label: '被守护人本人' },
                { value: 'guardian', label: '守护者' },
              ].map((opt) => {
                const active = setting.call_target === opt.value;
                return (
                  <button
                    key={opt.value}
                    data-testid={`bh-detail-call-target-${opt.value}`}
                    onClick={() => updateSetting({ call_target: opt.value })}
                    style={{
                      flex: 1, padding: '8px 0', borderRadius: 8,
                      background: active ? '#0EA5E9' : '#fff',
                      color: active ? '#fff' : '#374151',
                      border: active ? 'none' : '1px solid #d1d5db',
                      fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    }}
                  >{opt.label}</button>
                );
              })}
            </div>
          </div>
        </div>

        {/* 模块 2：TA 的设备（只读） */}
        <div
          style={{
            background: '#fff', borderRadius: 12, padding: 16, marginBottom: 12,
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            borderLeft: '3px solid #22c55e',
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>📱 TA 的设备</div>
          {deviceLoading ? (
            <div style={{ color: '#9ca3af', fontSize: 13 }}>加载中…</div>
          ) : devices.length === 0 ? (
            <div>
              <div style={{ color: '#9ca3af', fontSize: 13, padding: '8px 0' }}>
                TA 暂未绑定设备
              </div>
              <button
                data-testid="bh-detail-remind-bind"
                onClick={remindBind}
                style={{
                  marginTop: 8, padding: '10px 16px', background: '#0EA5E9', color: '#fff',
                  border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer',
                }}
              >提醒 TA 绑定设备 ›</button>
            </div>
          ) : (
            devices.map((d) => (
              <div
                key={d.id}
                style={{
                  padding: '10px 0', borderBottom: '1px solid #f3f4f6',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{d.device_name || d.device_type}</div>
                  <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 2 }}>
                    {d.last_sync_at ? `最后同步：${new Date(d.last_sync_at).toLocaleString()}` : '尚未同步数据'}
                  </div>
                </div>
                <span style={{ fontSize: 11, color: '#9ca3af' }}>只读</span>
              </div>
            ))
          )}
        </div>

        {/* 模块 3：解除守护 */}
        <button
          data-testid="bh-detail-cancel-management"
          onClick={cancelManagement}
          style={{
            width: '100%', padding: '12px 0', background: '#fff',
            color: '#ef4444', border: '1px solid #fecaca',
            borderRadius: 12, fontSize: 14, fontWeight: 600, cursor: 'pointer',
            marginTop: 16,
          }}
        >解除守护</button>
      </div>
    </div>
  );
}
