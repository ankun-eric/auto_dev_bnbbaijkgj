'use client';

/**
 * [PRD-420 2026-05-08] AI 对话模式 - 咨询对象选择器
 * [PRD-FAMILY-MEMBER-V2 2026-05-18] 重构：
 *   - 头像改为字徽方案（取关系字 + 分色，本人为「我」）
 *   - 副信息显示年龄而非出生日期：`关系 · 性别 · X 岁`
 *   - 顶部 3px 主色描边 + 大投影
 *   - 「新增家庭成员」入口复用 NewFamilyMemberModal（统一表单）
 */

import { useEffect, useState } from 'react';
import { Popup, Toast } from 'antd-mobile';
import api from '@/lib/api';
import MemberBadge from '@/components/family/MemberBadge';
import NewFamilyMemberModal from '@/components/health-profile-v5/NewFamilyMemberModal';
import { calcAge } from '@/lib/family-relation';
import { formatGender } from '@/utils/format';

export interface FamilyMemberItem {
  id: number;
  nickname: string;
  relationship_type?: string;
  relation_type_name?: string;
  birthday?: string;
  gender?: string;
  is_self: boolean;
}

interface ConsultTargetPickerProps {
  visible: boolean;
  onClose: () => void;
  /** 当前选中咨询对象的 family_member_id（本人时为 null） */
  currentMemberId: number | null;
  /** 选中已有成员（is_self=true 的本人 memberId 传 null） */
  onSelect: (member: FamilyMemberItem | null) => void;
  /**
   * [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F14 2026-05-18]
   * 候选列表排除当前咨询人：当前咨询人仍然显示在列表中，但置灰 + 名字后追加「（当前）」标注，
   * 整行不可点击。本组件内部直接根据 currentMemberId 判断。
   * 仅当 visible=true 时生效。
   */
}

export default function ConsultTargetPicker({
  visible,
  onClose,
  currentMemberId,
  onSelect,
}: ConsultTargetPickerProps) {
  const [members, setMembers] = useState<FamilyMemberItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  const fetchMembers = async () => {
    setLoading(true);
    setLoadFailed(false);
    try {
      const res: any = await api.get('/api/family/members');
      const data = res?.data || res;
      const list: FamilyMemberItem[] = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
      setMembers(list);
    } catch {
      setLoadFailed(true);
    }
    setLoading(false);
  };

  useEffect(() => {
    if (visible) fetchMembers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const handleSelectMember = (m: FamilyMemberItem) => {
    // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F14] 当前咨询人不可点击
    const isCurrent = m.is_self ? currentMemberId == null : m.id === currentMemberId;
    if (isCurrent) {
      try {
        Toast.show({ content: '该家庭成员已是当前咨询人', position: 'bottom' });
      } catch {}
      return;
    }
    onSelect(m.is_self ? null : m);
    onClose();
  };

  const handleAddSuccess = async () => {
    setShowAdd(false);
    await fetchMembers();
    Toast.show({ icon: 'success', content: '添加成功' });
  };

  if (showAdd) {
    return (
      <NewFamilyMemberModal
        onClose={() => setShowAdd(false)}
        onSuccess={handleAddSuccess}
      />
    );
  }

  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      position="bottom"
      bodyStyle={{
        borderRadius: '16px 16px 0 0',
        maxHeight: '72vh',
        overflowY: 'auto',
        borderTop: '3px solid #0EA5E9',
        boxShadow: '0 -20px 40px rgba(2,132,199,0.25)',
      }}
      data-testid="consult-target-picker"
    >
      <div className="px-4 pb-6">
        <div
          className="flex items-center justify-between py-3"
          style={{ borderBottom: '1px solid #F1F5F9' }}
        >
          <span className="text-base font-semibold" style={{ color: '#0F172A' }}>咨询人</span>
          <button
            onClick={onClose}
            className="text-xl leading-none"
            style={{ color: '#94A3B8' }}
            aria-label="关闭"
          >
            ×
          </button>
        </div>

        {loading && (
          <div className="py-6 text-center text-sm" style={{ color: '#94A3B8' }}>加载中...</div>
        )}

        {!loading && loadFailed && (
          <div className="py-8 flex flex-col items-center gap-3">
            <div className="text-sm" style={{ color: '#64748B' }}>加载失败</div>
            <button
              className="px-4 py-1.5 rounded-full text-xs"
              style={{ background: '#0EA5E9', color: '#fff' }}
              onClick={fetchMembers}
            >
              点击重试
            </button>
          </div>
        )}

        {!loading && !loadFailed && (
          <div className="mt-3 space-y-2">
            {members.map((m) => {
              const isCurrent = m.is_self ? currentMemberId == null : m.id === currentMemberId;
              const relationName = m.relation_type_name || m.relationship_type || '';
              const age = m.birthday ? calcAge(m.birthday) : null;
              // 副信息：`{关系名} · {性别} · {年龄} 岁`（本人为 `{性别} · {年龄} 岁`）
              const subParts: string[] = [];
              if (!m.is_self && relationName) subParts.push(relationName);
              if (m.gender) subParts.push(formatGender(m.gender) || '');
              if (age != null) subParts.push(`${age} 岁`);
              else subParts.push('-');
              const subText = subParts.filter(Boolean).join(' · ');
              const displayName = m.is_self ? '本人' : m.nickname;
              // [PRD-AIHOME-DRUG-IDENTIFY-OPTIM-V1 F14] 当前咨询人置灰 + (当前) 标注 + 不可点击
              const itemBg = isCurrent
                ? '#F1F5F9'
                : (m.is_self ? 'linear-gradient(135deg, #0EA5E9, #38BDF8)' : '#F8FAFC');
              const nameColor = isCurrent ? '#94A3B8' : (m.is_self ? '#fff' : '#0F172A');
              const subColor = isCurrent ? '#CBD5E1' : (m.is_self ? 'rgba(255,255,255,0.85)' : '#64748B');
              return (
                <div
                  key={`${m.id}-${m.is_self ? 'self' : 'mem'}`}
                  className="flex items-center gap-3 px-3 py-3 rounded-xl"
                  style={{
                    background: itemBg,
                    border: '1.5px solid transparent',
                    boxShadow: !isCurrent && m.is_self ? '0 4px 14px rgba(2,132,199,0.2)' : 'none',
                    opacity: isCurrent ? 0.7 : 1,
                    cursor: isCurrent ? 'not-allowed' : 'pointer',
                  }}
                  onClick={() => handleSelectMember(m)}
                  data-testid="consult-target-item"
                  data-current={isCurrent ? '1' : '0'}
                >
                  <MemberBadge
                    relationName={relationName}
                    name={m.nickname}
                    isSelf={m.is_self}
                    size={42}
                  />
                  <div className="flex-1 min-w-0">
                    <div
                      className="text-sm font-semibold truncate"
                      style={{ color: nameColor }}
                    >
                      {displayName}
                      {isCurrent && (
                        <span
                          style={{ marginLeft: 6, fontSize: 12, fontWeight: 500, color: '#94A3B8' }}
                          data-testid="consult-target-current-label"
                        >
                          （当前）
                        </span>
                      )}
                    </div>
                    <div
                      className="text-xs mt-1 truncate"
                      style={{ color: subColor }}
                    >
                      {subText}
                    </div>
                  </div>
                  {isCurrent && (
                    <span
                      className="text-base"
                      style={{
                        color: '#94A3B8',
                        fontWeight: 700,
                      }}
                      aria-label="当前选中"
                    >
                      ✓
                    </span>
                  )}
                </div>
              );
            })}

            <button
              onClick={() => setShowAdd(true)}
              data-testid="consult-target-add"
              style={{
                width: '100%',
                marginTop: 12,
                padding: '12px 14px',
                borderRadius: 24,
                background: 'linear-gradient(135deg, #38BDF8, #0284C7)',
                color: '#fff',
                fontSize: 15,
                fontWeight: 700,
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 6px 18px rgba(2,132,199,0.3), inset 0 1px 0 rgba(255,255,255,0.3)',
              }}
            >
              + 新增家庭成员
            </button>
          </div>
        )}
      </div>
    </Popup>
  );
}
