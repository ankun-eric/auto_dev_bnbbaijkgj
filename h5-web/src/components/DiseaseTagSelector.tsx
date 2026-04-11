'use client';

import { useState } from 'react';
import { Toast } from 'antd-mobile';

export type DiseaseItem = string | { type: 'custom'; value: string };

export function getItemName(item: DiseaseItem): string {
  return typeof item === 'string' ? item : item.value;
}

export function isCustomItem(item: DiseaseItem): boolean {
  return typeof item !== 'string' && item.type === 'custom';
}

export function isPresetSelected(items: DiseaseItem[], presetName: string): boolean {
  return items.some((i) => typeof i === 'string' && i === presetName);
}

export function getCustomItems(items: DiseaseItem[]): Array<{ type: 'custom'; value: string }> {
  return items.filter((i) => typeof i !== 'string') as Array<{ type: 'custom'; value: string }>;
}

interface DiseaseTagSelectorProps {
  items: DiseaseItem[];
  presets: { id: number; name: string }[];
  onChange: (items: DiseaseItem[]) => void;
  activeColor: string;
  categoryLabel: string;
}

export default function DiseaseTagSelector({
  items,
  presets,
  onChange,
  activeColor,
  categoryLabel,
}: DiseaseTagSelectorProps) {
  const [otherOpen, setOtherOpen] = useState(false);
  const [customInput, setCustomInput] = useState('');

  const togglePreset = (name: string) => {
    if (isPresetSelected(items, name)) {
      onChange(items.filter((i) => !(typeof i === 'string' && i === name)));
    } else {
      onChange([...items, name]);
    }
  };

  const handleAddCustom = () => {
    const val = customInput.trim();
    if (!val) {
      Toast.show({ content: '请输入内容' });
      return;
    }
    if (val.length > 100) {
      Toast.show({ content: '最多输入100个字符' });
      return;
    }
    if (presets.some((p) => p.name === val)) {
      Toast.show({ content: '该选项已存在于预设列表中，请直接选择' });
      return;
    }
    if (items.some((i) => getItemName(i) === val)) {
      Toast.show({ content: '该选项已添加' });
      return;
    }
    onChange([...items, { type: 'custom', value: val }]);
    setCustomInput('');
  };

  const removeCustom = (value: string) => {
    onChange(items.filter((i) => !(typeof i !== 'string' && i.type === 'custom' && i.value === value)));
  };

  const customItems = getCustomItems(items);

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {presets.map((p) => {
          const selected = isPresetSelected(items, p.name);
          return (
            <button
              key={p.id}
              className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
              style={{
                background: selected ? activeColor : '#f5f5f5',
                color: selected ? '#fff' : '#666',
              }}
              onClick={() => togglePreset(p.name)}
            >
              {p.name}
            </button>
          );
        })}
        <button
          className="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
          style={{
            background: otherOpen ? activeColor : '#f5f5f5',
            color: otherOpen ? '#fff' : '#666',
          }}
          onClick={() => setOtherOpen(!otherOpen)}
        >
          ✚ 其它
        </button>
      </div>

      {customItems.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {customItems.map((ci) => (
            <span
              key={ci.value}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium text-white"
              style={{ background: activeColor }}
            >
              {ci.value}
              <button
                className="ml-0.5 text-white/80 hover:text-white text-sm leading-none"
                onClick={() => removeCustom(ci.value)}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      {otherOpen && (
        <div className="flex gap-2 mt-2">
          <input
            className="flex-1 text-sm bg-gray-50 rounded-xl px-3 py-2 outline-none border border-gray-200"
            placeholder={`请输入其它${categoryLabel}…`}
            value={customInput}
            maxLength={100}
            onChange={(e) => setCustomInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleAddCustom();
            }}
          />
          <button
            className="px-4 py-2 rounded-xl text-xs font-medium text-white flex-shrink-0"
            style={{ background: activeColor }}
            onClick={handleAddCustom}
          >
            确认
          </button>
        </div>
      )}

      {presets.length === 0 && !otherOpen && customItems.length === 0 && (
        <p className="text-xs text-gray-400 text-center py-3">暂无预设选项</p>
      )}
    </div>
  );
}
