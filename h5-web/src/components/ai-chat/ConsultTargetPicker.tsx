'use client';

/**
 * [PRD-420 2026-05-08] AI 对话模式 - 咨询对象选择器
 * [PRD-FAMILY-MEMBER-V2 2026-05-18] 重构：
 *   - 头像改为字徽方案（取关系字 + 分色，本人为「我」）
 *   - 副信息显示年龄而非出生日期：`关系 · 性别 · X 岁`
 *   - 顶部 3px 主色描边 + 大投影
 *   - 「新增家庭成员」入口复用 NewFamilyMemberModal（统一表单）
 *
 * [PRD-AI-HOME-OPTIM-FINAL-V2 2026-05-19] AI 首页优化最终版：
 *   - 标题改为「选择咨询人」
 *   - 选中条统一使用蓝色渐变深色背景（不论本人/家人）
 *   - 未选中条统一使用浅灰底（本人不再有「天生蓝底」特权）
 *   - 主标题统一为「关系 · 姓名」格式（本人为「本人 · {姓名}」）
 *   - 右侧文字按钮：未选中态「选择」实心蓝底白字（醒目，可点击）；
 *     选中态「已选择」白底蓝字（禁用、置灰、无点击反馈）
 */

import { useEffect, useState } from 'react';
import { Popup } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
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
  // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G3]
  // 后端 /api/family/members 已返回 target_left=true 标记"对方已退出"
  target_left?: boolean;
  // 中文标签（如"对方已退出"），后端可选返回
  relation_status?: string;
}

interface ConsultTargetPickerProps {
  visible: boolean;
  onClose: () => void;
  /** 当前选中咨询对象的 family_member_id（本人时为 null） */
  currentMemberId: number | null;
  /** 选中已有成员（is_self=true 的本人 memberId 传 null） */
  onSelect: (member: FamilyMemberItem | null) => void;
}

// 与 --gradient-primary 同源的渐变
const PRIMARY_GRADIENT = 'linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)';

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
    // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G3] 对方已退出守护：
    //   不允许选为咨询对象，提示后早退（不进入原切换动画流程）
    if (m.target_left) {
      showToast('该对象已退出守护，无法进行 AI 咨询', 'fail');
      return;
    }
    // 已选中态：右侧「已选择」按钮置灰禁用，不响应点击
    const isCurrent = m.is_self ? currentMemberId == null : m.id === currentMemberId;
    if (isCurrent) {
      return;
    }
    onSelect(m.is_self ? null : m);
    onClose();
  };

  const handleAddSuccess = async () => {
    setShowAdd(false);
    await fetchMembers();
    showToast('添加成功');
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
          <span
            className="text-base font-semibold"
            style={{ color: '#0F172A' }}
            data-testid="consult-target-title"
          >
            选择咨询人
          </span>
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
            {/* [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G3] 视觉降权：
                target_left=true 的灰卡片排到末尾，与 i-guard 体验一致 */}
            {[...members]
              .sort((a, b) => {
                const al = a.target_left ? 1 : 0;
                const bl = b.target_left ? 1 : 0;
                return al - bl;
              })
              .map((m) => {
              const isCurrent = m.is_self ? currentMemberId == null : m.id === currentMemberId;
              const relationName = m.relation_type_name || m.relationship_type || (m.is_self ? '本人' : '');
              const age = m.birthday ? calcAge(m.birthday) : null;
              // 副信息：`{性别} · {年龄} 岁`
              const subParts: string[] = [];
              if (m.gender) subParts.push(formatGender(m.gender) || '');
              if (age != null) subParts.push(`${age} 岁`);
              else subParts.push('-');
              const subText = subParts.filter(Boolean).join(' · ');
              // 主标题：统一「关系 · 姓名」（兜底：关系空则仅姓名）
              const mainText = relationName ? `${relationName} · ${m.nickname}` : m.nickname;
              // [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29 G3] 对方已退出灰标
              const isLeft = !!m.target_left;
              // 选中：蓝色渐变；对方已退出：浅灰；未选中正常：浅灰
              const itemBg = isLeft
                ? '#F5F5F5'
                : isCurrent
                ? PRIMARY_GRADIENT
                : '#F8FAFC';
              const nameColor = isLeft ? '#999999' : isCurrent ? '#fff' : '#0F172A';
              const subColor = isLeft
                ? '#B0B0B0'
                : isCurrent
                ? 'rgba(255,255,255,0.85)'
                : '#64748B';
              return (
                <div
                  key={`${m.id}-${m.is_self ? 'self' : 'mem'}`}
                  className="flex items-center gap-3 px-3 py-3 rounded-xl"
                  style={{
                    background: itemBg,
                    border: '1.5px solid transparent',
                    boxShadow: isCurrent && !isLeft ? '0 4px 14px rgba(2,132,199,0.2)' : 'none',
                    cursor: isLeft ? 'not-allowed' : isCurrent ? 'default' : 'pointer',
                    opacity: isLeft ? 0.85 : 1,
                  }}
                  onClick={() => handleSelectMember(m)}
                  data-testid="consult-target-item"
                  data-current={isCurrent ? '1' : '0'}
                  data-target-left={isLeft ? '1' : '0'}
                >
                  <div style={{ filter: isLeft ? 'grayscale(80%)' : 'none' }}>
                    <MemberBadge
                      relationName={relationName}
                      name={m.nickname}
                      isSelf={m.is_self}
                      size={42}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div
                      className="text-sm font-semibold truncate"
                      style={{ color: nameColor }}
                      data-testid="consult-target-main-text"
                    >
                      {mainText}
                    </div>
                    <div
                      className="text-xs mt-1 truncate"
                      style={{ color: subColor }}
                    >
                      {isLeft ? (m.relation_status || '对方已退出') : subText}
                    </div>
                  </div>
                  {/*
                    右侧文字按钮：
                    - 选中态：白底 + 蓝字「已选择」，置灰禁用、无点击反馈
                    - 未选中态：实心蓝底 + 白字「选择」，可点击切换
                  */}
                  {isLeft ? (
                    <span
                      data-testid="consult-target-left-tag"
                      style={{
                        flexShrink: 0,
                        padding: '4px 10px',
                        borderRadius: 12,
                        background: '#E5E7EB',
                        color: '#6B7280',
                        fontSize: 11,
                        fontWeight: 600,
                        userSelect: 'none',
                        pointerEvents: 'none',
                      }}
                    >
                      对方已退出
                    </span>
                  ) : isCurrent ? (
                    <span
                      data-testid="consult-target-selected-btn"
                      style={{
                        flexShrink: 0,
                        padding: '6px 14px',
                        borderRadius: 16,
                        background: '#FFFFFF',
                        color: '#0284C7',
                        fontSize: 12,
                        fontWeight: 600,
                        opacity: 0.85,
                        cursor: 'default',
                        userSelect: 'none',
                        pointerEvents: 'none',
                      }}
                    >
                      已选择
                    </span>
                  ) : (
                    <button
                      type="button"
                      data-testid="consult-target-select-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSelectMember(m);
                      }}
                      style={{
                        flexShrink: 0,
                        padding: '6px 14px',
                        borderRadius: 16,
                        background: '#0284C7',
                        color: '#FFFFFF',
                        fontSize: 12,
                        fontWeight: 600,
                        border: 'none',
                        cursor: 'pointer',
                        boxShadow: '0 2px 6px rgba(2,132,199,0.25)',
                      }}
                    >
                      选择
                    </button>
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
