'use client';

import { Popup, Slider } from 'antd-mobile';
import { FontLevel } from '@/lib/useFontSize';

interface FontSettingPopupProps {
  visible: boolean;
  onClose: () => void;
  fontLevel: FontLevel;
  onFontLevelChange: (level: FontLevel) => void;
  standardSize: number;
  largeSize: number;
  xlargeSize: number;
}

const LEVELS: FontLevel[] = ['standard', 'large', 'xlarge'];
// v6: 档位文案语义化升级
const LABELS: Record<FontLevel, string> = {
  standard: '标准',
  large: '大字号 👨‍🦳',
  xlarge: '超大字号 👴',
};
const PREVIEW_HINTS: Record<FontLevel, string> = {
  standard: '日常阅读舒适',
  large: '中年人阅读更轻松',
  xlarge: '长辈/视力不佳者首选',
};

function levelToValue(level: FontLevel): number {
  return LEVELS.indexOf(level);
}

function valueToLevel(val: number): FontLevel {
  return LEVELS[val] || 'standard';
}

function getSizeForLevel(level: FontLevel, s: number, l: number, xl: number): number {
  switch (level) {
    case 'large': return l;
    case 'xlarge': return xl;
    default: return s;
  }
}

export default function FontSettingPopup({
  visible,
  onClose,
  fontLevel,
  onFontLevelChange,
  standardSize,
  largeSize,
  xlargeSize,
}: FontSettingPopupProps) {
  const currentSize = getSizeForLevel(fontLevel, standardSize, largeSize, xlargeSize);

  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: '20px 16px 32px' }}
      position="bottom"
    >
      <div className="flex items-center justify-between mb-4">
        <span className="text-base font-bold">字体大小</span>
        <span className="text-sm text-gray-400" onClick={onClose}>关闭</span>
      </div>

      <div
        className="bg-gray-50 rounded-xl p-4 mb-4"
        style={{ fontSize: currentSize }}
      >
        <p className="mb-2">预览文字效果</p>
        <p className="text-gray-500">宾尼小康，AI健康管家，关爱您的每一天。</p>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-4">
        {LEVELS.map((lv) => {
          const size = getSizeForLevel(lv, standardSize, largeSize, xlargeSize);
          const active = fontLevel === lv;
          return (
            <div
              key={lv}
              onClick={() => onFontLevelChange(lv)}
              style={{
                border: `1.5px solid ${active ? '#52c41a' : '#e5e7eb'}`,
                background: active ? '#E8F7EE' : '#fff',
                borderRadius: 12,
                padding: '10px 8px',
                textAlign: 'center',
                cursor: 'pointer',
              }}
            >
              <div
                style={{
                  fontSize: size,
                  fontWeight: 600,
                  color: active ? '#389e0d' : '#333',
                  lineHeight: 1.2,
                }}
              >
                {LABELS[lv]}
              </div>
              <div className="text-xs text-gray-400 mt-1">{PREVIEW_HINTS[lv]}</div>
            </div>
          );
        })}
      </div>

      <div className="px-2">
        <Slider
          min={0}
          max={2}
          step={1}
          value={levelToValue(fontLevel)}
          onChange={(val) => {
            onFontLevelChange(valueToLevel(val as number));
          }}
          ticks
          style={{
            '--fill-color': '#52c41a',
          } as React.CSSProperties}
        />
        <div className="flex justify-between mt-2">
          {LEVELS.map((lv) => (
            <span
              key={lv}
              className={`text-xs ${fontLevel === lv ? 'text-green-600 font-medium' : 'text-gray-400'}`}
            >
              {LABELS[lv]}
            </span>
          ))}
        </div>
      </div>
    </Popup>
  );
}
