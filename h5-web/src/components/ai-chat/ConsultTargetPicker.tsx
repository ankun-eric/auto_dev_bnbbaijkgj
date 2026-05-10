'use client';

/**
 * [PRD-420 2026-05-08] AI 对话模式 - 咨询对象选择器（公共组件）
 *
 * 把菜单模式中已经成熟的"咨询对象选择 + 添加家庭成员（关系九宫格 + 信息表单）"
 * 抽取为独立公共组件，使 AI 对话模式（ai-home）与菜单模式（chat/[sessionId]）
 * 可以共用同一份组件、同一份接口、同一份字段字典；保证两种模式 100% 体验一致。
 *
 * 数据来源：
 *   - GET /api/family/members           获取家庭成员（已按 is_self 优先 + created_at 正序）
 *   - GET /api/relation-types           获取关系字典（除"本人"外）
 *   - POST /api/family/members          新增家庭成员
 *
 * 全部接口与菜单模式 100% 共用，无后端改造。
 */

import { useEffect, useRef, useState } from 'react';
import { Popup, Toast, Tag, DatePicker } from 'antd-mobile';
import api from '@/lib/api';

export interface FamilyMemberItem {
  id: number;
  nickname: string;
  relationship_type?: string;
  relation_type_name?: string;
  is_self: boolean;
}

interface RelationTypeItem {
  id: number;
  name: string;
  sort_order?: number;
}

interface ConsultTargetPickerProps {
  visible: boolean;
  onClose: () => void;
  /** 当前选中咨询对象的 family_member_id（本人时为 null） */
  currentMemberId: number | null;
  /** 选中已有成员（is_self=true 的本人 memberId 传 null） */
  onSelect: (member: FamilyMemberItem | null) => void;
}

const RELATION_EMOJI: Record<string, string> = {
  '本人': '👤',
  '爸爸': '👨',
  '妈妈': '👩',
  '老公': '🧑',
  '老婆': '👰',
  '儿子': '👦',
  '女儿': '👧',
  '哥哥': '👱‍♂️',
  '弟弟': '🧑',
  '姐姐': '👱‍♀️',
  '妹妹': '👧',
  '爷爷': '👴',
  '奶奶': '👵',
  '外公': '👴',
  '外婆': '👵',
  '其他': '🧑',
};

function getRelationEmoji(name: string): string {
  return RELATION_EMOJI[name] || '🧑';
}

function getRelationColor(relation: string): string {
  if (relation === '本人') return '#0EA5E9';
  if (['爸爸', '妈妈', '父亲', '母亲'].includes(relation)) return '#1890ff';
  if (['儿子', '女儿', '子女'].includes(relation)) return '#eb2f96';
  if (['爷爷', '奶奶', '外公', '外婆'].includes(relation)) return '#fa8c16';
  if (['老公', '老婆', '配偶'].includes(relation)) return '#722ed1';
  return '#8c8c8c';
}

const ADD_MEDICAL_OPTIONS = ['高血压', '糖尿病', '心脏病', '哮喘', '甲状腺疾病', '肝病', '肾病', '痛风'];
const ADD_ALLERGY_OPTIONS = ['青霉素', '花粉', '海鲜', '牛奶', '尘螨', '坚果', '磺胺类', '头孢类'];

export default function ConsultTargetPicker({
  visible,
  onClose,
  currentMemberId,
  onSelect,
}: ConsultTargetPickerProps) {
  const [members, setMembers] = useState<FamilyMemberItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  // 子抽屉：添加家庭成员
  const [addVisible, setAddVisible] = useState(false);
  const [relationTypes, setRelationTypes] = useState<RelationTypeItem[]>([]);
  const [selectedRelation, setSelectedRelation] = useState<RelationTypeItem | null>(null);
  const [newNickname, setNewNickname] = useState('');
  const [newGender, setNewGender] = useState('');
  const [newBirthday, setNewBirthday] = useState('');
  const [newBirthdayPickerVisible, setNewBirthdayPickerVisible] = useState(false);
  const [newHeight, setNewHeight] = useState('');
  const [newWeight, setNewWeight] = useState('');
  const [newMedicalHistories, setNewMedicalHistories] = useState<string[]>([]);
  const [newMedicalOther, setNewMedicalOther] = useState('');
  const [newAllergies, setNewAllergies] = useState<string[]>([]);
  const [newAllergyOther, setNewAllergyOther] = useState('');
  const [addLoading, setAddLoading] = useState(false);
  const [confirmDiscardVisible, setConfirmDiscardVisible] = useState(false);

  const formDirtyRef = useRef(false);

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

  const fetchRelationTypes = async () => {
    try {
      const res: any = await api.get('/api/relation-types');
      const data = res?.data || res;
      const items: RelationTypeItem[] = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
      // 过滤掉"本人"，避免重复
      setRelationTypes(items.filter((rt) => rt.name !== '本人'));
    } catch {
      setRelationTypes([]);
    }
  };

  // 每次打开均重新拉取（确保多端数据一致：H5 打开时若小程序已新增，立即可见）
  useEffect(() => {
    if (visible) {
      fetchMembers();
    }
    // 关闭时不立即清空，避免再次打开时空白闪烁
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const handleSelectMember = (m: FamilyMemberItem) => {
    onSelect(m.is_self ? null : m);
    onClose();
  };

  const openAdd = async () => {
    setAddVisible(true);
    setSelectedRelation(null);
    setNewNickname('');
    setNewGender('');
    setNewBirthday('');
    setNewHeight('');
    setNewWeight('');
    setNewMedicalHistories([]);
    setNewMedicalOther('');
    setNewAllergies([]);
    setNewAllergyOther('');
    formDirtyRef.current = false;
    await fetchRelationTypes();
  };

  const isFormDirty = (): boolean => {
    return !!(
      selectedRelation ||
      newNickname.trim() ||
      newGender ||
      newBirthday ||
      newHeight ||
      newWeight ||
      newMedicalHistories.length > 0 ||
      newMedicalOther ||
      newAllergies.length > 0 ||
      newAllergyOther
    );
  };

  const handleCloseAdd = () => {
    if (isFormDirty()) {
      setConfirmDiscardVisible(true);
      return;
    }
    setAddVisible(false);
  };

  const confirmDiscard = () => {
    setConfirmDiscardVisible(false);
    setAddVisible(false);
  };

  const handleSaveNew = async () => {
    if (!selectedRelation) {
      Toast.show({ icon: 'fail', content: '请先选择关系' });
      return;
    }
    const nickname = newNickname.trim();
    if (!nickname) {
      Toast.show({ icon: 'fail', content: '请填写姓名' });
      return;
    }
    if (nickname.length < 1 || nickname.length > 20) {
      Toast.show({ icon: 'fail', content: '姓名为 1~20 个字符' });
      return;
    }
    if (!newGender) {
      Toast.show({ icon: 'fail', content: '请选择性别' });
      return;
    }
    if (!newBirthday) {
      Toast.show({ icon: 'fail', content: '请选择出生日期' });
      return;
    }
    // 校验身高/体重范围
    if (newHeight) {
      const h = Number(newHeight);
      if (!Number.isFinite(h) || h < 30 || h > 250) {
        Toast.show({ icon: 'fail', content: '身高范围 30~250cm' });
        return;
      }
    }
    if (newWeight) {
      const w = Number(newWeight);
      if (!Number.isFinite(w) || w < 1 || w > 500) {
        Toast.show({ icon: 'fail', content: '体重范围 1~500kg' });
        return;
      }
    }

    // 同关系（如"老婆"）反复添加柔性提示
    const sameRelationCount = members.filter(
      (m) => !m.is_self && (m.relation_type_name || m.relationship_type) === selectedRelation.name,
    ).length;
    if (sameRelationCount > 0) {
      const ok = window.confirm(`已有 ${sameRelationCount} 位「${selectedRelation.name}」，是否仍添加？`);
      if (!ok) return;
    }

    setAddLoading(true);
    try {
      const body: any = {
        nickname,
        name: nickname,
        relationship_type: selectedRelation.name,
        relation_type_id: selectedRelation.id,
        gender: newGender,
        birthday: newBirthday,
      };
      if (newHeight) body.height = Number(newHeight);
      if (newWeight) body.weight = Number(newWeight);
      const medicals = [...newMedicalHistories];
      if (newMedicalOther.trim()) medicals.push(newMedicalOther.trim());
      if (medicals.length) body.medical_histories = medicals;
      const allergies = [...newAllergies];
      if (newAllergyOther.trim()) allergies.push(newAllergyOther.trim());
      if (allergies.length) body.allergies = allergies;

      const res: any = await api.post('/api/family/members', body);
      const data = res?.data || res;
      // 保存成功 → 子抽屉关闭 + 列表刷新 + 自动选中新成员
      setAddVisible(false);
      await fetchMembers();
      const newMember: FamilyMemberItem = {
        id: data?.id ?? 0,
        nickname: data?.nickname || nickname,
        relationship_type: data?.relationship_type || selectedRelation.name,
        relation_type_name: data?.relation_type_name || selectedRelation.name,
        is_self: false,
      };
      Toast.show({ icon: 'success', content: '成员添加成功' });
      // F4 验收：保存成功立即触发选中流程（语义即"为他咨询"）
      onSelect(newMember);
      onClose();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '添加失败，请重试';
      Toast.show({ icon: 'fail', content: typeof detail === 'string' ? detail : '添加失败，请重试' });
    }
    setAddLoading(false);
  };

  const saveDisabled = !selectedRelation || !newNickname.trim() || !newGender || !newBirthday || addLoading;

  return (
    <>
      {/* P2: 切换咨询对象抽屉 */}
      <Popup
        visible={visible && !addVisible}
        onMaskClick={onClose}
        position="bottom"
        bodyStyle={{ borderRadius: '16px 16px 0 0', maxHeight: '70vh', overflowY: 'auto' }}
        data-testid="consult-target-picker"
      >
        <div className="px-4 pb-6">
          <div className="flex items-center justify-between py-4 border-b border-gray-100">
            <span className="text-base font-semibold">切换咨询对象</span>
            <button
              onClick={onClose}
              className="text-gray-400 text-xl leading-none"
              aria-label="关闭"
            >
              ×
            </button>
          </div>

          {loading && (
            <div className="py-6 text-center text-sm text-gray-400">加载中...</div>
          )}

          {!loading && loadFailed && (
            <div className="py-8 flex flex-col items-center gap-3">
              <div className="text-sm text-gray-500">加载失败</div>
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
                const relationLabel = m.relation_type_name || m.relationship_type || '本人';
                const emoji = m.is_self ? '👤' : getRelationEmoji(relationLabel);
                const displayName = m.is_self ? '本人' : `${relationLabel} · ${m.nickname}`;
                const isCurrent = m.is_self ? currentMemberId == null : m.id === currentMemberId;
                return (
                  <div
                    key={`${m.id}-${m.is_self ? 'self' : 'mem'}`}
                    className="flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer"
                    style={{ background: isCurrent ? '#f0f9eb' : '#f9f9f9' }}
                    onClick={() => handleSelectMember(m)}
                    data-testid="consult-target-item"
                  >
                    <div
                      className="w-9 h-9 rounded-full flex items-center justify-center text-xl"
                      style={{
                        background: m.is_self ? 'linear-gradient(135deg, #0EA5E9, #38BDF8)' : '#87d068',
                      }}
                    >
                      {m.is_self ? <span className="text-white text-sm">我</span> : emoji}
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-medium">{displayName}</div>
                      {m.is_self && (
                        <div
                          className="text-xs"
                          style={{ color: '#999' }}
                        >
                          本人
                        </div>
                      )}
                    </div>
                    {isCurrent && (
                      <span
                        className="text-base"
                        style={{ color: '#0EA5E9', fontWeight: 700 }}
                        aria-label="当前选中"
                      >
                        ✓
                      </span>
                    )}
                  </div>
                );
              })}

              <div
                className="flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer"
                style={{ background: '#f9f9f9' }}
                onClick={openAdd}
                data-testid="consult-target-add"
              >
                <div
                  className="w-9 h-9 rounded-full flex items-center justify-center text-white text-lg"
                  style={{ background: '#0EA5E9' }}
                >
                  +
                </div>
                <span className="text-sm font-medium" style={{ color: '#0EA5E9' }}>
                  新建家庭成员
                </span>
              </div>
            </div>
          )}
        </div>
      </Popup>

      {/* P3 + P4: 添加家庭成员（选关系 + 填信息） */}
      <Popup
        visible={visible && addVisible}
        onMaskClick={handleCloseAdd}
        position="bottom"
        bodyStyle={{ borderRadius: '20px 20px 0 0', maxHeight: '90vh', overflowY: 'auto' }}
      >
        <div className="px-4 pb-8">
          <div className="flex items-center justify-between py-4 border-b border-gray-100">
            <span className="text-base font-bold text-gray-800">添加家庭成员</span>
            <button
              className="text-gray-400 text-2xl leading-none"
              onClick={handleCloseAdd}
              aria-label="关闭"
            >
              ×
            </button>
          </div>

          <div className="mt-4">
            <div className="text-sm font-semibold text-gray-700 mb-3">选择关系</div>
            <div className="grid grid-cols-4 gap-3">
              {relationTypes.map((rt) => {
                const emoji = getRelationEmoji(rt.name);
                const isSelected = selectedRelation?.id === rt.id;
                return (
                  <button
                    key={rt.id}
                    className="flex flex-col items-center py-2 rounded-xl transition-all"
                    style={{
                      background: isSelected ? 'linear-gradient(135deg, #F0F9FF, #e6fffb)' : '#f9f9f9',
                      border: isSelected ? '1.5px solid #0EA5E9' : '1.5px solid transparent',
                    }}
                    onClick={() =>
                      setSelectedRelation((cur) => (cur?.id === rt.id ? null : rt))
                    }
                  >
                    <span className="text-2xl">{emoji}</span>
                    <span className="text-xs mt-1" style={{ color: isSelected ? '#0EA5E9' : '#555' }}>
                      {rt.name}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {selectedRelation && (
            <div
              className="mt-5 p-4 rounded-2xl"
              style={{ background: '#F0F9FF', border: '1px solid #BAE6FD' }}
            >
              <div className="text-sm font-semibold mb-4" style={{ color: '#0EA5E9' }}>
                {getRelationEmoji(selectedRelation.name)} 填写{selectedRelation.name}信息
              </div>

              <div className="space-y-3">
                <div>
                  <div className="text-xs text-gray-500 mb-1">
                    姓名 <span style={{ color: '#ff4d4f' }}>*</span>
                  </div>
                  <input
                    className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200"
                    placeholder="请输入姓名（1~20 字）"
                    value={newNickname}
                    maxLength={20}
                    onChange={(e) => setNewNickname(e.target.value)}
                  />
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">
                    性别 <span style={{ color: '#ff4d4f' }}>*</span>
                  </div>
                  <div className="flex gap-3">
                    {(['male', 'female'] as const).map((g) => (
                      <button
                        key={g}
                        className="flex-1 py-2 rounded-xl text-sm font-medium transition-all"
                        style={{
                          background:
                            newGender === g ? 'linear-gradient(135deg, #0EA5E9, #38BDF8)' : '#fff',
                          color: newGender === g ? '#fff' : '#666',
                          border: `1px solid ${newGender === g ? '#0EA5E9' : '#e8e8e8'}`,
                        }}
                        onClick={() => setNewGender(g)}
                      >
                        {g === 'male' ? '男' : '女'}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">
                    出生日期 <span style={{ color: '#ff4d4f' }}>*</span>
                  </div>
                  <button
                    className="w-full bg-white text-sm rounded-xl px-3 py-2 text-left border border-gray-200 flex items-center justify-between"
                    onClick={() => setNewBirthdayPickerVisible(true)}
                  >
                    <span style={{ color: newBirthday ? '#333' : '#bbb' }}>
                      {newBirthday || '请选择出生日期'}
                    </span>
                    <span>📅</span>
                  </button>
                </div>

                <div className="flex gap-3">
                  <div className="flex-1">
                    <div className="text-xs text-gray-500 mb-1">身高 (cm)</div>
                    <input
                      type="number"
                      className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200"
                      placeholder="如：170"
                      value={newHeight}
                      onChange={(e) => setNewHeight(e.target.value)}
                    />
                  </div>
                  <div className="flex-1">
                    <div className="text-xs text-gray-500 mb-1">体重 (kg)</div>
                    <input
                      type="number"
                      className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200"
                      placeholder="如：65"
                      value={newWeight}
                      onChange={(e) => setNewWeight(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">既往病史</div>
                  <div className="flex flex-wrap gap-2">
                    {ADD_MEDICAL_OPTIONS.map((opt) => (
                      <Tag
                        key={opt}
                        onClick={() =>
                          setNewMedicalHistories((prev) =>
                            prev.includes(opt) ? prev.filter((x) => x !== opt) : [...prev, opt],
                          )
                        }
                        style={{
                          '--background-color': newMedicalHistories.includes(opt) ? '#0EA5E9' : '#fff',
                          '--text-color': newMedicalHistories.includes(opt) ? '#fff' : '#666',
                          '--border-color': newMedicalHistories.includes(opt) ? '#0EA5E9' : '#d9d9d9',
                          padding: '4px 10px',
                          borderRadius: 14,
                          fontSize: 12,
                          cursor: 'pointer',
                        } as any}
                      >
                        {opt}
                      </Tag>
                    ))}
                  </div>
                  <input
                    className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200 mt-2"
                    placeholder="其他病史（可选）"
                    value={newMedicalOther}
                    onChange={(e) => setNewMedicalOther(e.target.value)}
                  />
                </div>

                <div>
                  <div className="text-xs text-gray-500 mb-1">过敏史</div>
                  <div className="flex flex-wrap gap-2">
                    {ADD_ALLERGY_OPTIONS.map((opt) => (
                      <Tag
                        key={opt}
                        onClick={() =>
                          setNewAllergies((prev) =>
                            prev.includes(opt) ? prev.filter((x) => x !== opt) : [...prev, opt],
                          )
                        }
                        style={{
                          '--background-color': newAllergies.includes(opt) ? '#0EA5E9' : '#fff',
                          '--text-color': newAllergies.includes(opt) ? '#fff' : '#666',
                          '--border-color': newAllergies.includes(opt) ? '#0EA5E9' : '#d9d9d9',
                          padding: '4px 10px',
                          borderRadius: 14,
                          fontSize: 12,
                          cursor: 'pointer',
                        } as any}
                      >
                        {opt}
                      </Tag>
                    ))}
                  </div>
                  <input
                    className="w-full bg-white text-sm rounded-xl px-3 py-2 outline-none border border-gray-200 mt-2"
                    placeholder="其他过敏史（可选）"
                    value={newAllergyOther}
                    onChange={(e) => setNewAllergyOther(e.target.value)}
                  />
                </div>
              </div>

              <button
                className="w-full mt-4 py-3 rounded-2xl text-white font-semibold text-sm"
                style={{
                  background: saveDisabled
                    ? '#d9d9d9'
                    : 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
                  cursor: saveDisabled ? 'not-allowed' : 'pointer',
                }}
                disabled={saveDisabled}
                onClick={handleSaveNew}
              >
                {addLoading ? '保存中...' : '保存'}
              </button>
            </div>
          )}
        </div>
      </Popup>

      {/* 出生日期选择 */}
      <DatePicker
        visible={newBirthdayPickerVisible}
        onClose={() => setNewBirthdayPickerVisible(false)}
        precision="day"
        max={new Date()}
        min={new Date('1900-01-01')}
        title="选择出生日期"
        onConfirm={(val) => {
          const d = val as Date;
          const str = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
          setNewBirthday(str);
          setNewBirthdayPickerVisible(false);
        }}
      />

      {/* 二次确认丢弃 */}
      {confirmDiscardVisible && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 2000,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onClick={() => setConfirmDiscardVisible(false)}
        >
          <div
            className="bg-white rounded-2xl px-6 py-5 mx-6"
            style={{ maxWidth: 320, width: '85%' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-base font-semibold mb-2">确认离开？</div>
            <div className="text-sm text-gray-600 mb-4">未保存的内容将丢失</div>
            <div className="flex gap-3 justify-end">
              <button
                className="px-4 py-2 rounded-lg text-sm"
                style={{ background: '#f5f5f5', color: '#666' }}
                onClick={() => setConfirmDiscardVisible(false)}
              >
                取消
              </button>
              <button
                className="px-4 py-2 rounded-lg text-sm text-white"
                style={{ background: '#ff4d4f' }}
                onClick={confirmDiscard}
              >
                确认离开
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
