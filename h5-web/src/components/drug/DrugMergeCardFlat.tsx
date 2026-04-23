'use client';

import { Toast } from 'antd-mobile';

export interface DrugListItem {
  id?: number | null;
  name: string;
  image_url?: string | null;
}

export interface MemberInfo {
  nickname?: string | null;
  age?: number | null;
  gender?: string | null;
  relationship_type?: string | null;
}

interface Props {
  drugs: DrugListItem[];
  memberInfo?: MemberInfo | null;
  onImageClick: (index: number) => void;
}

const RELATION_EMOJI: Record<string, string> = {
  self: '👤', 本人: '👤', 爸爸: '👨', 妈妈: '👩', 父亲: '👨', 母亲: '👩',
  老公: '👨', 老婆: '👩', 配偶: '💑',
  儿子: '👦', 女儿: '👧', 子女: '👧',
  哥哥: '👱‍♂️', 弟弟: '🧑', 姐姐: '👱‍♀️', 妹妹: '👧',
  爷爷: '👴', 奶奶: '👵', 外公: '👴', 外婆: '👵', 其他: '🧑',
};

function memberEmoji(m?: MemberInfo | null): string {
  if (!m) return '👤';
  const key = m.relationship_type || '';
  return RELATION_EMOJI[key] || '🧑';
}

function memberLine(m?: MemberInfo | null): string {
  if (!m) return '本人';
  const name = m.nickname || '本人';
  const age = typeof m.age === 'number' ? `${m.age}岁` : '';
  return age ? `${name} · ${age}` : name;
}

export default function DrugMergeCardFlat({ drugs, memberInfo, onImageClick }: Props) {
  const list = (drugs || []).slice(0, 2);
  const single = list.length <= 1;

  const showFullName = (name: string) => {
    Toast.show({ content: name, duration: 2000 });
  };

  return (
    <div
      className="bg-white rounded-2xl p-3 shadow-sm"
      style={{ border: '1px solid #f0f0f0' }}
    >
      <div className="flex gap-3">
        {/* 左侧 40%: 药图 */}
        <div className="flex items-center justify-center" style={{ width: '40%' }}>
          {list.length === 0 ? (
            <div
              className="flex items-center justify-center rounded-xl bg-gray-100"
              style={{ width: 140, height: 140, border: '1px solid #eee' }}
            >
              <span className="text-3xl">💊</span>
            </div>
          ) : single ? (
            <button
              onClick={() => list[0]?.image_url && onImageClick(0)}
              className="p-0 bg-transparent border-0"
              style={{ cursor: list[0]?.image_url ? 'zoom-in' : 'default' }}
            >
              {list[0]?.image_url ? (
                <img
                  src={list[0].image_url}
                  alt={list[0].name}
                  style={{
                    width: 140,
                    height: 140,
                    objectFit: 'cover',
                    borderRadius: 12,
                    border: '1px solid #eee',
                  }}
                />
              ) : (
                <div
                  className="flex items-center justify-center bg-gray-100"
                  style={{
                    width: 140,
                    height: 140,
                    borderRadius: 12,
                    border: '1px solid #eee',
                  }}
                >
                  <span className="text-3xl">💊</span>
                </div>
              )}
            </button>
          ) : (
            <div className="flex items-center" style={{ gap: 4 }}>
              {list.map((d, i) => (
                <button
                  key={i}
                  onClick={() => d.image_url && onImageClick(i)}
                  className="p-0 bg-transparent border-0"
                  style={{ cursor: d.image_url ? 'zoom-in' : 'default' }}
                >
                  {d.image_url ? (
                    <img
                      src={d.image_url}
                      alt={d.name}
                      style={{
                        width: 68,
                        height: 140,
                        objectFit: 'cover',
                        borderRadius: 12,
                        border: '1px solid #eee',
                      }}
                    />
                  ) : (
                    <div
                      className="flex items-center justify-center bg-gray-100"
                      style={{
                        width: 68,
                        height: 140,
                        borderRadius: 12,
                        border: '1px solid #eee',
                      }}
                    >
                      <span className="text-xl">💊</span>
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 右侧 60%: 对象 + 药名列表 */}
        <div className="flex-1 min-w-0 flex flex-col justify-center">
          <div className="flex items-center gap-2 mb-2">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-lg flex-shrink-0"
              style={{ background: '#f6ffed', border: '1px solid #d9f7be' }}
            >
              {memberEmoji(memberInfo)}
            </div>
            <div className="text-[15px] font-medium truncate" style={{ color: '#333' }}>
              {memberLine(memberInfo)}
            </div>
          </div>

          <div className="space-y-1.5">
            {list.length === 0 ? (
              <div className="text-[15px] text-gray-400">暂无药品</div>
            ) : single ? (
              <button
                className="w-full text-left p-0 bg-transparent border-0"
                onClick={() => showFullName(list[0].name)}
              >
                <div
                  className="text-[15px] font-medium truncate"
                  style={{ color: '#333' }}
                  title={list[0].name}
                >
                  💊 {list[0].name}
                </div>
              </button>
            ) : (
              list.map((d, i) => (
                <button
                  key={i}
                  className="w-full text-left p-0 bg-transparent border-0"
                  onClick={() => showFullName(d.name)}
                >
                  <div
                    className="text-[15px] font-medium truncate"
                    style={{ color: '#333' }}
                    title={d.name}
                  >
                    💊 药{i + 1}：{d.name}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
