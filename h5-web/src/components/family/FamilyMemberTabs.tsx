'use client';

/**
 * [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] v1.0
 * [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-V2 2026-05-29] v2.0
 *   - Bug 3：成员 Tab 对齐健康档案 MemberBadge（字徽 + 关系字 + 辈分分色）
 * [BUGFIX HOME-SAFETY-ADD-MEMBER-WHITESCREEN 2026-05-29] v3.0
 *   - Bug：居家安全设备页点击「+ 添加」白屏 "gateway ok"
 *   - 根因：之前 handleAdd 用 window.location.href='/health-profile'
 *     在 basePath（/autodev/xxx）下漏掉前缀，请求打到网关未注册路径
 *     得到兜底文本 "gateway ok"，渲染为白屏
 *   - 修复：抽出公共「新增家庭成员」逻辑——直接打开 NewFamilyMemberModal
 *     与健康档案页同名按钮行为完全一致（弹窗加家人，不跳页、不绑设备）
 *
 * 公共家庭成员 Tab 组件
 *
 * 用途：健康档案、居家安全等页面共用的"成员 Tab"
 * 数据源：统一调用 /api/family/members（与健康档案对齐）
 *
 * 视觉规则（与健康档案保持像素级一致）：
 * - 未选中：圆形字徽（36px）+ 下方关系名（13px 灰色）
 * - 选中：字徽放大 1.06×、底部 6px 阴影、关系名变主色 + 字重 600、Tab 底部 3px 主色下划线
 * - 「+ 添加」为虚线圆 + 「添加」文字
 */
import { useCallback, useEffect, useState } from 'react';
import api from '@/lib/api';
import { showToast } from '@/lib/toast-unified';
import MemberBadge from './MemberBadge';
import NewFamilyMemberModal from '@/components/health-profile-v5/NewFamilyMemberModal';

export interface FamilyMemberLite {
  id: number;
  nickname: string;
  relationship_type?: string;
  relation_type_name?: string;
  is_self?: boolean;
}

interface Props {
  activeMemberId: number | null;
  onChange: (memberId: number) => void;
  showAddTab?: boolean;
  onAddClick?: () => void;
  /** 同时把成员列表回传给父组件 */
  onMembersLoaded?: (members: FamilyMemberLite[]) => void;
  className?: string;
}

const BRAND_PRIMARY = '#0EA5E9';

function memberLabel(m: FamilyMemberLite): string {
  if (m.is_self) return '本人';
  return m.relation_type_name || m.relationship_type || m.nickname || '家人';
}

export default function FamilyMemberTabs({
  activeMemberId,
  onChange,
  showAddTab = true,
  onAddClick,
  onMembersLoaded,
  className,
}: Props) {
  const [members, setMembers] = useState<FamilyMemberLite[]>([]);
  // [BUGFIX HOME-SAFETY-ADD-MEMBER-WHITESCREEN 2026-05-29] 内嵌新增家庭成员弹窗
  const [showAddMember, setShowAddMember] = useState(false);

  const load = useCallback(async () => {
    try {
      const r: any = await api.get('/api/family/members');
      const items: FamilyMemberLite[] = (r as any)?.items ?? (r as any)?.data?.items ?? [];
      setMembers(items);
      if (onMembersLoaded) onMembersLoaded(items);
      if (activeMemberId == null) {
        const selfM = items.find((m) => m.is_self);
        if (selfM) onChange(selfM.id);
      }
    } catch (e: any) {
      console.error('[FamilyMemberTabs] load fail:', e?.message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // [BUGFIX HOME-SAFETY-ADD-MEMBER-WHITESCREEN 2026-05-29]
  // 抽出公共「新增家庭成员」逻辑：默认打开 NewFamilyMemberModal 弹窗
  // 与健康档案页同名按钮一致；父组件可通过 onAddClick 覆盖
  const handleAdd = () => {
    if (onAddClick) {
      onAddClick();
      return;
    }
    setShowAddMember(true);
  };

  const handleAddSuccess = () => {
    setShowAddMember(false);
    showToast('已添加家庭成员');
    load();
  };

  return (
    <div
      className={className}
      style={{
        display: 'flex',
        gap: 14,
        padding: '12px 16px 8px',
        overflowX: 'auto',
        background: '#fff',
        borderBottom: '1px solid #EEE',
      }}
      data-testid="family-member-tabs"
    >
      {members.map((m) => {
        const active = activeMemberId === m.id;
        const label = memberLabel(m);
        return (
          <button
            key={m.id}
            onClick={() => onChange(m.id)}
            data-testid={`fmt-tab-${m.id}`}
            data-active={active ? '1' : '0'}
            style={{
              flex: '0 0 auto',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 4,
              padding: '4px 6px 6px',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              position: 'relative',
              minWidth: 52,
            }}
          >
            <div
              style={{
                transform: active ? 'scale(1.06)' : 'scale(1)',
                transition: 'transform 120ms ease',
                filter: active ? 'drop-shadow(0 6px 4px rgba(14,165,233,0.25))' : 'none',
              }}
            >
              <MemberBadge
                relationName={m.relation_type_name || m.relationship_type || ''}
                name={m.nickname}
                isSelf={!!m.is_self}
                size={36}
                fontSize={15}
                showPlaceholderTag={false}
              />
            </div>
            <span
              style={{
                fontSize: 13,
                color: active ? BRAND_PRIMARY : '#666',
                fontWeight: active ? 600 : 400,
                lineHeight: 1.2,
                whiteSpace: 'nowrap',
              }}
            >
              {label}
            </span>
            {active ? (
              <span
                style={{
                  position: 'absolute',
                  left: '50%',
                  bottom: -2,
                  transform: 'translateX(-50%)',
                  width: 22,
                  height: 3,
                  background: BRAND_PRIMARY,
                  borderRadius: 2,
                }}
              />
            ) : null}
          </button>
        );
      })}
      {showAddTab ? (
        <button
          onClick={handleAdd}
          data-testid="fmt-add"
          style={{
            flex: '0 0 auto',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 4,
            padding: '4px 6px 6px',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            minWidth: 52,
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: '50%',
              border: '1.5px dashed #BBB',
              color: '#999',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 20,
              fontWeight: 400,
              background: '#fff',
              boxSizing: 'border-box',
            }}
          >
            +
          </div>
          <span style={{ fontSize: 13, color: '#999', lineHeight: 1.2, whiteSpace: 'nowrap' }}>
            添加
          </span>
        </button>
      ) : null}
      {/* [BUGFIX HOME-SAFETY-ADD-MEMBER-WHITESCREEN 2026-05-29] 内嵌新增家庭成员弹窗 */}
      {showAddMember ? (
        <NewFamilyMemberModal
          onClose={() => setShowAddMember(false)}
          onSuccess={handleAddSuccess}
        />
      ) : null}
    </div>
  );
}
