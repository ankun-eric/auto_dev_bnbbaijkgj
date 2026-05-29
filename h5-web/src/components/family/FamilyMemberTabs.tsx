'use client';

/**
 * [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29]
 * 公共家庭成员 Tab 组件
 *
 * 用途：健康档案、居家安全等页面共用的"成员 Tab"
 * 数据源：统一调用 /api/family/members（与健康档案对齐）
 * 兼容：兼容 home-safety 旧返回结构（items: MemberItem[]）
 */
import { useCallback, useEffect, useState } from 'react';
import api from '@/lib/api';

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

function memberLabel(m: FamilyMemberLite): string {
  if (m.is_self) return '本人';
  // 优先使用关系名（如「父亲」「母亲」），其次使用昵称
  return m.relation_type_name || m.nickname || m.relationship_type || '家人';
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

  const load = useCallback(async () => {
    try {
      const r: any = await api.get('/api/family/members');
      const items: FamilyMemberLite[] = (r as any)?.items ?? (r as any)?.data?.items ?? [];
      setMembers(items);
      if (onMembersLoaded) onMembersLoaded(items);
      // 默认激活本人
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

  const handleAdd = () => {
    if (onAddClick) {
      onAddClick();
      return;
    }
    try {
      // 默认跳转到健康档案添加成员
      window.location.href = '/health-profile';
    } catch {}
  };

  return (
    <div
      className={className}
      style={{
        display: 'flex',
        gap: 8,
        padding: '12px 16px',
        overflowX: 'auto',
        background: '#fff',
        borderBottom: '1px solid #EEE',
      }}
    >
      {members.map((m) => {
        const active = activeMemberId === m.id;
        return (
          <button
            key={m.id}
            onClick={() => onChange(m.id)}
            style={{
              flex: '0 0 auto',
              padding: '8px 16px',
              background: active ? '#1F8FE6' : '#F4F6F8',
              color: active ? '#fff' : '#333',
              border: 'none',
              borderRadius: 16,
              fontSize: 13,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              fontWeight: active ? 600 : 400,
            }}
          >
            {memberLabel(m)}
          </button>
        );
      })}
      {showAddTab ? (
        <button
          onClick={handleAdd}
          style={{
            flex: '0 0 auto',
            padding: '8px 12px',
            background: '#F4F6F8',
            color: '#666',
            border: '1px dashed #BBB',
            borderRadius: 16,
            fontSize: 13,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          + 添加
        </button>
      ) : null}
    </div>
  );
}
