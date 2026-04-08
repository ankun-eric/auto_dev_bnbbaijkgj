'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { SpinLoading } from 'antd-mobile';
import axios from 'axios';

interface DrugInfo {
  name: string;
  ingredients?: string;
  specification?: string;
  indications?: string;
  dosage?: string;
  precautions?: string;
  ai_suggestion_general?: string;
  ai_suggestion_personal?: string | null;
}

interface DrugInteraction {
  drugs: string[];
  risk: string;
}

interface DrugAiResult {
  drugs: DrugInfo[];
  interactions?: DrugInteraction[];
}

interface SharedDrugData {
  record_id?: number;
  drug_name?: string | null;
  drug_category?: string | null;
  dosage?: string | null;
  precautions?: string | null;
  ai_structured_result?: string | DrugAiResult | null;
  original_image_url?: string | null;
  created_at?: string;
  view_count?: number;
  expired?: boolean;
}

const DISCLAIMER = '⚠️ 仅供参考，不构成医疗建议。如有疑问，请咨询专业医生或药师。';
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

function parseAiResult(raw: string | DrugAiResult | null | undefined): DrugAiResult | null {
  if (!raw) return null;
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }
  return raw;
}

function InfoRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <span
        className="text-xs font-medium mr-1"
        style={{ color: highlight ? '#FF4D4F' : '#52c41a' }}
      >
        {label}
      </span>
      <span className="text-xs text-gray-600 leading-relaxed">{value}</span>
    </div>
  );
}

function SharedDrugCard({ drug }: { drug: DrugInfo }) {
  return (
    <div
      className="rounded-xl bg-white overflow-hidden"
      style={{ border: '1px solid #f0f0f0', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}
    >
      <div className="px-4 py-3" style={{ background: 'linear-gradient(135deg, #52c41a18, #13c2c218)' }}>
        <h3 className="font-bold text-base text-gray-800">{drug.name}</h3>
        {drug.specification && (
          <p className="text-xs text-gray-400 mt-0.5">{drug.specification}</p>
        )}
      </div>

      <div className="px-4 py-3 space-y-2.5">
        {drug.ingredients && <InfoRow label="主要成分" value={drug.ingredients} />}
        {drug.indications && <InfoRow label="适应症" value={drug.indications} />}
        {drug.dosage && <InfoRow label="用法用量" value={drug.dosage} />}
        {drug.precautions && <InfoRow label="注意事项" value={drug.precautions} highlight />}
      </div>

      {drug.ai_suggestion_general && (
        <div className="border-t px-4 pb-4 pt-3" style={{ borderColor: '#f0f0f0' }}>
          <p className="text-xs font-medium mb-1" style={{ color: '#52c41a' }}>通用建议</p>
          <p className="text-sm text-gray-600 leading-relaxed">{drug.ai_suggestion_general}</p>
        </div>
      )}
    </div>
  );
}

export default function SharedDrugPage() {
  const params = useParams();
  const token = params.token as string;

  const [data, setData] = useState<SharedDrugData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedIdx, setExpandedIdx] = useState<number | null>(0);

  useEffect(() => {
    if (!token) return;
    fetchData();
  }, [token]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${basePath}/api/drug-identify/share/${token}`);
      const result = res.data;
      if (result.expired) {
        setError('链接已过期');
        return;
      }
      setData(result);
    } catch (err: any) {
      if (err?.response?.status === 404 || err?.response?.status === 410) {
        setError('链接已过期或不存在');
      } else {
        setError('加载失败，请稍后重试');
      }
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <SpinLoading style={{ '--size': '36px', '--color': '#52c41a' }} />
          <p className="text-sm text-gray-400 mt-4">加载中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center px-6">
          <div className="text-5xl mb-4">⏰</div>
          <p className="text-base text-gray-500">{error}</p>
          <p className="text-xs text-gray-300 mt-3">请联系分享者重新生成链接</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const aiResult = parseAiResult(data.ai_structured_result);
  const drugs = aiResult?.drugs || [];
  const interactions = aiResult?.interactions || [];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Brand header */}
      <div
        className="px-4 py-5"
        style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0"
          >
            <span className="text-white text-sm font-bold">💊</span>
          </div>
          <div>
            <h1 className="text-white font-bold text-base">bini-health 健康平台</h1>
            <p className="text-white/70 text-xs mt-0.5">药物识别解读报告</p>
          </div>
        </div>
      </div>

      <div className="px-4 py-4 space-y-4">
        {/* Drug interaction warning */}
        {interactions.length > 0 && (
          <div
            className="rounded-xl px-4 py-3"
            style={{ background: '#FFFBE6', border: '1px solid #FFE58F' }}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-base">⚠️</span>
              <span className="font-semibold text-sm" style={{ color: '#FAAD14' }}>
                药物相互作用提示
              </span>
            </div>
            <div className="space-y-2">
              {interactions.map((inter, idx) => (
                <div key={idx} className="text-xs text-gray-600">
                  <span className="font-medium text-gray-700">
                    {inter.drugs.join(' + ')}：
                  </span>
                  {inter.risk}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Drug cards */}
        {drugs.length === 0 && (
          <div className="text-center py-10 text-gray-400 text-sm">暂无药物识别数据</div>
        )}

        {drugs.length === 1 ? (
          <SharedDrugCard drug={drugs[0]} />
        ) : (
          <div className="space-y-3">
            {drugs.map((drug, idx) => (
              <div key={idx}>
                <button
                  className="w-full text-left rounded-xl bg-white px-4 py-3 flex items-center justify-between"
                  style={{ border: '1px solid #f0f0f0' }}
                  onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                >
                  <div>
                    <span className="font-semibold text-sm text-gray-800">{drug.name}</span>
                    {drug.specification && (
                      <span className="text-xs text-gray-400 ml-2">{drug.specification}</span>
                    )}
                  </div>
                  <span className="text-gray-400 text-sm">
                    {expandedIdx === idx ? '▲' : '▼'}
                  </span>
                </button>
                {expandedIdx === idx && (
                  <div className="mt-1">
                    <SharedDrugCard drug={drug} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Fallback: raw text if no structured data */}
        {!aiResult && data.ai_structured_result && typeof data.ai_structured_result === 'string' && (
          <div className="rounded-xl bg-white p-4" style={{ border: '1px solid #f0f0f0' }}>
            <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">
              {data.ai_structured_result}
            </p>
          </div>
        )}

        {/* Disclaimer */}
        <div className="rounded-xl bg-amber-50 p-3">
          <p className="text-xs text-amber-700 leading-relaxed">{DISCLAIMER}</p>
        </div>
      </div>

      {/* Brand footer */}
      <div className="border-t border-gray-100 bg-white px-4 py-4 text-center mt-4">
        <div className="flex items-center justify-center gap-2">
          <span className="text-lg">🌿</span>
          <span
            className="font-bold text-sm"
            style={{
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            宾尼小康 AI健康管家
          </span>
        </div>
        <p className="text-[11px] text-gray-300 mt-1">
          此为分享内容，仅供参考，不构成医疗建议
        </p>
      </div>
    </div>
  );
}
