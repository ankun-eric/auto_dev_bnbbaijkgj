'use client';
/**
 * [PRD-HEALTH-ARCHIVE-CO-MANAGE 2026-06-05] 「我的设备」V3 主页面（场景分类版）。
 *
 * 设计要点：
 * - 按四大场景分类展示：安全守护 / 健康守护 / 日夜守护 / 其他
 * - 每个分类卡片右上角显示"已绑 X 台"
 * - 分类下无设备时显示"暂无设备"占位
 * - 禁用的分类不展示
 * - 点击设备卡片跳转到 jump_url 指定的详情页
 * - 底部保留"支持设备列表"按品牌展示（兼容旧版）
 */
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import {
  bindDevice,
  editBinding,
  fetchCatalog,
  fetchMyDevices,
  fetchSceneGroups,
  unbindDevice,
  type BindPayload,
  type CatalogGroup,
  type CatalogItem,
  type EditBindingPayload,
  type MyDeviceItem,
  type SceneGroup,
} from '@/lib/api/devices';
import BrandSection from './components/BrandSection';
import MyDeviceCard from './components/MyDeviceCard';
import BindDeviceDrawer from './components/BindDeviceDrawer';
import EditDeviceDrawer from './components/EditDeviceDrawer';
import UnbindConfirmModal from './components/UnbindConfirmModal';
import { DV_COLOR } from './components/theme';

export default function DevicesPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>加载中…</div>}>
      <DevicesPageInner />
    </Suspense>
  );
}

const SCENE_ICONS: Record<string, string> = {
  '安全守护': '🛡️',
  '健康守护': '💚',
  '日夜守护': '🌙',
  '其他': '📱',
};

function DevicesPageInner() {
  const searchParams = useSearchParams();
  const memberId = searchParams?.get('member_id') || '';
  const isSelfTab = !memberId || memberId === '0';
  const [myList, setMyList] = useState<MyDeviceItem[]>([]);
  const [groups, setGroups] = useState<CatalogGroup[]>([]);
  const [sceneGroups, setSceneGroups] = useState<SceneGroup[]>([]);
  const [loading, setLoading] = useState(true);

  const [bindTarget, setBindTarget] = useState<CatalogItem | null>(null);
  const [editTarget, setEditTarget] = useState<MyDeviceItem | null>(null);
  const [unbindTarget, setUnbindTarget] = useState<MyDeviceItem | null>(null);
  const [unbindSubmitting, setUnbindSubmitting] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const mid = isSelfTab ? undefined : memberId;
      const [my, cat, sg] = await Promise.all([
        fetchMyDevices(mid).catch(() => ({ items: [], total: 0 })),
        fetchCatalog().catch(() => ({ groups: [], total: 0 })),
        fetchSceneGroups().catch(() => ({ items: [], total: 0 })),
      ]);
      setMyList(my.items || []);
      setGroups(cat.groups || []);
      setSceneGroups(sg.items || []);
    } finally {
      setLoading(false);
    }
  }, [memberId, isSelfTab]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleBindClick = (item: CatalogItem) => {
    setBindTarget(item);
  };

  const handleBindSubmit = async (payload: BindPayload) => {
    try {
      await bindDevice(payload);
      showToast('绑定成功');
      setBindTarget(null);
      await loadAll();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.response?.data?.message || e?.message || '绑定失败';
      showToast(String(msg), 'fail');
    }
  };

  const handleEditSubmit = async (payload: EditBindingPayload) => {
    if (!editTarget) return;
    try {
      await editBinding(editTarget.id, payload);
      showToast('已保存');
      setEditTarget(null);
      await loadAll();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '保存失败';
      showToast(String(msg), 'fail');
    }
  };

  const handleUnbindConfirm = async () => {
    if (!unbindTarget) return;
    setUnbindSubmitting(true);
    try {
      await unbindDevice(unbindTarget.id);
      showToast('已解绑');
      setUnbindTarget(null);
      await loadAll();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '解绑失败';
      showToast(String(msg), 'fail');
    } finally {
      setUnbindSubmitting(false);
    }
  };

  // 按场景分组我的设备
  const devicesByScene = useMemo(() => {
    const map: Record<number, MyDeviceItem[]> = {};
    const ungrouped: MyDeviceItem[] = [];
    for (const d of myList) {
      const sgid = d.scene_group_id;
      if (sgid != null && sgid > 0) {
        if (!map[sgid]) map[sgid] = [];
        map[sgid].push(d);
      } else {
        ungrouped.push(d);
      }
    }
    return { map, ungrouped };
  }, [myList]);

  const enabledSceneGroups = useMemo(
    () => sceneGroups.filter((sg) => sg.is_enabled),
    [sceneGroups],
  );

  // 其他分类（scene_group_id 为最后一项，通常是"其他"）
  const otherGroup = enabledSceneGroups.length > 0
    ? enabledSceneGroups[enabledSceneGroups.length - 1]
    : null;

  const myDeviceCount = useMemo(() => myList.length, [myList]);

  return (
    <div style={{ background: DV_COLOR.brand50, minHeight: '100vh', paddingBottom: 32 }}>
      <GreenNavBar>我的设备</GreenNavBar>

      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* 区域一：按场景分类已绑定设备 */}
        <section>
          <div style={{
            display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
            marginBottom: 10,
          }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: DV_COLOR.textPrimary, margin: 0 }}>
              我的设备
            </h2>
            <span style={{ fontSize: 12, color: DV_COLOR.textSecondary }}>
              已绑定 {myDeviceCount} 台
            </span>
          </div>

          {loading ? (
            <div style={{
              background: '#fff', borderRadius: 16, padding: 32, textAlign: 'center',
              color: DV_COLOR.textSecondary, boxShadow: '0 2px 12px rgba(2,132,199,0.06)',
            }}>加载中…</div>
          ) : enabledSceneGroups.length === 0 ? (
            <div style={{
              background: '#fff', borderRadius: 16, padding: 28, textAlign: 'center',
              color: DV_COLOR.textSecondary,
            }}>
              <div style={{ fontSize: 56, marginBottom: 8 }}>📱➕</div>
              <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>还没有绑定任何设备</div>
              <div style={{ fontSize: 13, opacity: 0.92 }}>从下方支持设备列表选择并绑定设备</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {enabledSceneGroups.map((sg) => {
                const sgDevices = devicesByScene.map[sg.id] || [];
                const isOther = otherGroup && sg.id === otherGroup.id;
                const allDevices = isOther
                  ? [...sgDevices, ...devicesByScene.ungrouped]
                  : sgDevices;
                return (
                  <SceneGroupCard
                    key={sg.id}
                    name={sg.name}
                    devices={allDevices}
                    onEdit={(d) => setEditTarget(d)}
                    onUnbind={(d) => setUnbindTarget(d)}
                  />
                );
              })}
            </div>
          )}
        </section>

        {/* 区域二：支持设备列表（按品牌） */}
        <section data-testid="bh-brand-catalog-section">
          <h2 style={{
            fontSize: 16, fontWeight: 600, color: DV_COLOR.textPrimary,
            margin: '4px 0 12px 0',
          }}>
            支持设备列表
          </h2>
          {loading && groups.length === 0 ? (
            <div style={{
              background: '#fff', borderRadius: 16, padding: 32, textAlign: 'center',
              color: DV_COLOR.textSecondary,
            }}>加载中…</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {groups.map((g) => (
                <BrandSection key={g.brand_code} group={g} onBind={handleBindClick} />
              ))}
              {groups.length === 0 && (
                <div style={{
                  background: '#fff', borderRadius: 16, padding: 24, textAlign: 'center',
                  color: DV_COLOR.textSecondary, fontSize: 13,
                }}>暂无可绑定设备</div>
              )}
            </div>
          )}
        </section>
      </div>

      <BindDeviceDrawer
        visible={!!bindTarget}
        catalog={bindTarget}
        onClose={() => setBindTarget(null)}
        onSubmit={handleBindSubmit}
      />
      <EditDeviceDrawer
        visible={!!editTarget}
        item={editTarget}
        onClose={() => setEditTarget(null)}
        onSubmit={handleEditSubmit}
      />
      <UnbindConfirmModal
        visible={!!unbindTarget}
        item={unbindTarget}
        submitting={unbindSubmitting}
        onCancel={() => setUnbindTarget(null)}
        onConfirm={handleUnbindConfirm}
      />
    </div>
  );
}

// ───────────── 场景分类卡片 ─────────────

function SceneGroupCard({
  name,
  devices,
  onEdit,
  onUnbind,
}: {
  name: string;
  devices: MyDeviceItem[];
  onEdit: (d: MyDeviceItem) => void;
  onUnbind: (d: MyDeviceItem) => void;
}) {
  const icon = SCENE_ICONS[name] || '📱';
  const count = devices.length;

  return (
    <div style={{
      background: '#fff',
      borderRadius: 16,
      padding: '16px 16px 12px',
      boxShadow: '0 2px 12px rgba(2,132,199,0.06)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: count > 0 ? 12 : 6,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 22 }}>{icon}</span>
          <span style={{ fontSize: 15, fontWeight: 600, color: '#0F172A' }}>{name}</span>
        </div>
        <span style={{
          fontSize: 12, color: DV_COLOR.brand600,
          background: '#E0F2FE', padding: '3px 10px', borderRadius: 10,
          fontWeight: 500,
        }}>
          已绑 {count} 台
        </span>
      </div>

      {count === 0 ? (
        <div style={{
          textAlign: 'center', padding: '16px 0', color: '#94A3B8', fontSize: 13,
        }}>
          暂无设备
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 10,
        }}>
          {devices.map((d) => (
            <MyDeviceCard
              key={d.id}
              item={d}
              onEdit={(x) => onEdit(x)}
              onUnbind={(x) => onUnbind(x)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
