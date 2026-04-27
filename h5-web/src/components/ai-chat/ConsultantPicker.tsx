'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Popup, Avatar } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import api from '@/lib/api';

interface FamilyMember {
  id: number;
  nickname: string;
  relationship_type: string;
  relation_type_name: string;
  avatar?: string;
  is_self: boolean;
}

interface ConsultantPickerProps {
  visible: boolean;
  onClose: () => void;
  onSelect: (member: FamilyMember) => void;
}

const RELATION_AVATAR: Record<string, string> = {
  '本人': '👤',
  '爸爸': '👨',
  '妈妈': '👩',
  '老公': '🧑',
  '老婆': '👩',
  '儿子': '👦',
  '女儿': '👧',
};

export default function ConsultantPicker({ visible, onClose, onSelect }: ConsultantPickerProps) {
  const router = useRouter();
  const [members, setMembers] = useState<FamilyMember[]>([]);

  useEffect(() => {
    if (!visible) return;
    api.get('/api/family/members').then((res: any) => {
      const data = res.data || res;
      setMembers(Array.isArray(data.items) ? data.items : []);
    }).catch(() => {});
  }, [visible]);

  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      position="bottom"
      bodyStyle={{ borderRadius: '20px 20px 0 0', maxHeight: '50vh' }}
    >
      <div className="px-4 pb-6">
        <div className="flex items-center justify-between py-4 border-b" style={{ borderColor: THEME.divider }}>
          <span className="text-base font-bold" style={{ color: THEME.textPrimary }}>选择咨询人</span>
          <button className="text-2xl leading-none" style={{ color: THEME.textSecondary }} onClick={onClose}>×</button>
        </div>

        <div className="py-3 space-y-2 max-h-64 overflow-y-auto">
          {members.map(member => {
            const relation = member.relation_type_name || member.relationship_type || '本人';
            const emoji = RELATION_AVATAR[relation] || '🧑';
            return (
              <div
                key={member.id}
                className="flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer active:opacity-70"
                style={{ background: THEME.primaryLight }}
                onClick={() => { onSelect(member); onClose(); }}
              >
                <div
                  className="flex items-center justify-center rounded-full text-lg"
                  style={{ width: 40, height: 40, background: THEME.primary, color: '#fff' }}
                >
                  {member.avatar ? (
                    <Avatar src={member.avatar} style={{ '--size': '40px', '--border-radius': '50%' }} />
                  ) : emoji}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium" style={{ color: THEME.textPrimary }}>{member.nickname}</div>
                  <div className="text-xs" style={{ color: THEME.textSecondary }}>{relation}</div>
                </div>
              </div>
            );
          })}
        </div>

        <div
          className="flex items-center justify-center gap-2 py-3 mt-2 rounded-xl cursor-pointer"
          style={{ border: `1px dashed ${THEME.primary}`, color: THEME.primary }}
          onClick={() => { onClose(); router.push('/family-bindlist'); }}
        >
          <span className="text-lg">+</span>
          <span className="text-sm">添加新成员</span>
        </div>
      </div>
    </Popup>
  );
}
