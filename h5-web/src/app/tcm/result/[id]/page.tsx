'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button, SpinLoading, Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';

/**
 * 体质测评结果页（一期 · 6 屏）。
 * 数据来源：后端 `/api/constitution/result/{id}` 聚合接口。
 *
 * 屏 1：体质名片（拟人形象 + 雷达图 + 一句话描述）
 * 屏 2：深度解读（特征 + 成因）
 * 屏 3：个性化养生方案（饮食 / 作息 / 运动 / 情志）
 * 屏 4：专属膳食套餐推荐
 * 屏 5：广州门店服务（领券 + 预约）
 * 屏 6：分享卡
 */

interface Persona {
  emoji?: string;
  avatar_keyword?: string;
  color?: string;
  one_line?: string;
}

interface PackageCard {
  sku_id: number | null;
  sku_kind: 'product' | 'service' | null;
  name: string;
  price: number | null;
  original_price: number | null;
  image: string | null;
  description: string | null;
  reason: string;
  reason_tag_color: string;
  matched: boolean;
}

interface CouponState {
  available: boolean;
  status: 'claimable' | 'claimed' | 'used' | 'unavailable';
  message: string;
  coupon_id: number | null;
  user_coupon_id?: number;
  validity_days?: number;
  expire_at?: string;
}

interface ResultData {
  diagnosis_id: number;
  created_at: string;
  member_label: string;
  screen1_card: {
    type: string;
    persona: Persona;
    one_line_desc: string;
    short_desc: string;
    color: string;
    radar: { dimensions: string[]; scores: number[] };
  };
  screen2_analysis: {
    features: {
      external?: string[];
      internal?: string[];
      easy_problems?: string[];
    };
    causes: { innate?: string; acquired?: string };
    ai_summary?: string;
  };
  screen3_plan: {
    diet: { good?: string[]; avoid?: string[] };
    lifestyle: string[];
    exercise: { name: string; frequency: string }[];
    emotion: string[];
    ai_extra?: string;
  };
  screen4_packages: PackageCard[];
  screen5_store: {
    city_restricted: boolean;
    available_city: string;
    coupon: CouponState;
    appointment_hint: string;
    non_guangzhou_fallback_text: string;
  };
  screen6_share: {
    title: string;
    subtitle: string;
    persona: Persona;
    radar_preview: { dimensions: string[]; scores: number[] };
    slogan: string;
    qr_hint: string;
  };
  disclaimer: string;
}

// ══════════════════════════════════════════════════════════
// 雷达图 SVG 组件（零依赖）
// ══════════════════════════════════════════════════════════
function RadarChart({
  dimensions,
  scores,
  color = '#52c41a',
  size = 220,
}: {
  dimensions: string[];
  scores: number[];
  color?: string;
  size?: number;
}) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.38;
  const n = dimensions.length;
  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const point = (i: number, v: number) => {
    const vv = Math.max(0, Math.min(100, v)) / 100;
    return [cx + r * vv * Math.cos(angle(i)), cy + r * vv * Math.sin(angle(i))];
  };

  // 背景同心多边形（4 层）
  const rings = [0.25, 0.5, 0.75, 1.0];

  // 计分点
  const pts = scores.map((v, i) => point(i, v));
  const polygon = pts.map((p) => `${p[0]},${p[1]}`).join(' ');

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {rings.map((ratio, ri) => {
        const bgPts = Array.from({ length: n }, (_, i) => {
          const x = cx + r * ratio * Math.cos(angle(i));
          const y = cy + r * ratio * Math.sin(angle(i));
          return `${x},${y}`;
        }).join(' ');
        return (
          <polygon
            key={ri}
            points={bgPts}
            fill="none"
            stroke="#e8e8e8"
            strokeWidth={1}
          />
        );
      })}
      {Array.from({ length: n }, (_, i) => {
        const x = cx + r * Math.cos(angle(i));
        const y = cy + r * Math.sin(angle(i));
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={x}
            y2={y}
            stroke="#e8e8e8"
            strokeWidth={1}
          />
        );
      })}
      <polygon
        points={polygon}
        fill={color}
        fillOpacity={0.25}
        stroke={color}
        strokeWidth={2}
      />
      {pts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r={3} fill={color} />
      ))}
      {dimensions.map((d, i) => {
        const x = cx + (r + 16) * Math.cos(angle(i));
        const y = cy + (r + 16) * Math.sin(angle(i));
        return (
          <text
            key={d}
            x={x}
            y={y}
            fontSize={11}
            fill="#555"
            textAnchor="middle"
            dominantBaseline="middle"
          >
            {d}
          </text>
        );
      })}
    </svg>
  );
}

// ══════════════════════════════════════════════════════════
// 分享卡海报（Canvas 生成，用于保存图片）
// ══════════════════════════════════════════════════════════
async function generateShareCard(data: ResultData): Promise<string> {
  const w = 750;
  const h = 1334;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';

  // 背景（国风渐变）
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, '#f6ffed');
  grad.addColorStop(0.5, '#fff');
  grad.addColorStop(1, '#e6fffb');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);

  // 顶部装饰
  ctx.fillStyle = data.screen1_card.color || '#52c41a';
  ctx.globalAlpha = 0.1;
  ctx.fillRect(0, 0, w, 200);
  ctx.globalAlpha = 1;

  // emoji
  ctx.font = '120px serif';
  ctx.textAlign = 'center';
  ctx.fillText(data.screen1_card.persona.emoji || '🌿', w / 2, 220);

  // 标题
  ctx.fillStyle = data.screen1_card.color || '#52c41a';
  ctx.font = 'bold 64px "PingFang SC", sans-serif';
  ctx.fillText(data.screen1_card.type, w / 2, 320);

  // 副标题
  ctx.fillStyle = '#666';
  ctx.font = '28px "PingFang SC", sans-serif';
  const subtitle = data.screen1_card.one_line_desc || '';
  ctx.fillText(subtitle.length > 18 ? subtitle.slice(0, 18) + '…' : subtitle, w / 2, 380);

  // 雷达图（简化）：在中部画 9 维得分条
  const barTop = 450;
  const barLeft = 100;
  const barW = 550;
  const dims = data.screen1_card.radar.dimensions;
  const scores = data.screen1_card.radar.scores;
  for (let i = 0; i < dims.length; i++) {
    const y = barTop + i * 50;
    ctx.fillStyle = '#eee';
    ctx.fillRect(barLeft + 80, y + 14, barW - 80, 16);
    ctx.fillStyle = data.screen1_card.color || '#52c41a';
    const ww = ((barW - 80) * Math.max(0, Math.min(100, scores[i]))) / 100;
    ctx.fillRect(barLeft + 80, y + 14, ww, 16);
    ctx.fillStyle = '#333';
    ctx.font = '22px "PingFang SC", sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(dims[i], barLeft, y + 24);
  }

  // 分隔线
  ctx.strokeStyle = '#ddd';
  ctx.beginPath();
  ctx.moveTo(80, 1020);
  ctx.lineTo(w - 80, 1020);
  ctx.stroke();

  // Slogan
  ctx.fillStyle = '#52c41a';
  ctx.font = 'bold 40px "PingFang SC", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(data.screen6_share.slogan || '一起测，测完约个艾灸', w / 2, 1100);

  // 品牌
  ctx.fillStyle = '#888';
  ctx.font = '24px "PingFang SC", sans-serif';
  ctx.fillText('宾尼小康 · 中医养生', w / 2, 1160);

  // 二维码占位框
  ctx.strokeStyle = '#52c41a';
  ctx.lineWidth = 3;
  ctx.strokeRect(w / 2 - 70, 1200, 140, 140);
  ctx.font = '20px "PingFang SC", sans-serif';
  ctx.fillStyle = '#52c41a';
  ctx.fillText('扫码测体质', w / 2, 1360 - 20);

  return canvas.toDataURL('image/png');
}

// ══════════════════════════════════════════════════════════
// 主页面
// ══════════════════════════════════════════════════════════
export default function TcmResultPage() {
  const router = useRouter();
  const params = useParams();
  const id = Array.isArray(params?.id) ? params.id[0] : (params?.id as string);

  const [data, setData] = useState<ResultData | null>(null);
  const [loading, setLoading] = useState(true);
  const [claimingCoupon, setClaimingCoupon] = useState(false);
  const [shareVisible, setShareVisible] = useState(false);
  const [shareImageUrl, setShareImageUrl] = useState<string | null>(null);
  const [generatingShare, setGeneratingShare] = useState(false);

  const fetchResult = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get(`/api/constitution/result/${id}`);
      setData(res.data || res);
    } catch (err: any) {
      Toast.show({ content: '加载结果失败，请稍后重试', icon: 'fail' });
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) fetchResult();
  }, [id, fetchResult]);

  const handleClaimCoupon = async () => {
    if (claimingCoupon || !data) return;
    setClaimingCoupon(true);
    try {
      const res: any = await api.post('/api/constitution/coupon/claim');
      const r = res.data || res;
      if (r.success) {
        Toast.show({
          content: r.already_claimed ? '您已领取过该券' : '领取成功，请到「我的优惠券」查看',
          icon: 'success',
        });
        await fetchResult();
      } else {
        Toast.show({ content: '领取失败，请稍后重试', icon: 'fail' });
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || '领取失败，请稍后重试';
      Toast.show({ content: String(msg), icon: 'fail' });
    } finally {
      setClaimingCoupon(false);
    }
  };

  const handleBookAppointment = () => {
    if (!data) return;
    // 跳转到预约页，带 source 参数便于后端统计转化
    router.push('/unified-orders?source=tizhi_test&project=moxibustion');
  };

  const handleViewCoupons = () => {
    router.push('/my-coupons');
  };

  const handleBuyPackage = (pkg: PackageCard) => {
    if (!pkg.matched || !pkg.sku_id) {
      Toast.show({ content: '套餐暂未上架，敬请期待' });
      return;
    }
    if (pkg.sku_kind === 'product') {
      router.push(`/product-detail/${pkg.sku_id}?source=tizhi_test`);
    } else {
      router.push(`/service-detail/${pkg.sku_id}?source=tizhi_test`);
    }
  };

  const handleShare = async () => {
    if (!data) return;
    setShareVisible(true);
    if (shareImageUrl) return;
    setGeneratingShare(true);
    try {
      const url = await generateShareCard(data);
      setShareImageUrl(url);
    } finally {
      setGeneratingShare(false);
    }
  };

  const handleSaveShareImage = () => {
    if (!shareImageUrl) return;
    const a = document.createElement('a');
    a.href = shareImageUrl;
    a.download = `constitution_${data?.screen1_card.type || 'share'}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    Toast.show({ content: '已保存到本地，可分享到朋友圈', icon: 'success' });
  };

  if (loading || !data) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar back={() => router.back()}>体质分析报告</GreenNavBar>
        <div className="flex flex-col items-center justify-center py-32">
          <SpinLoading style={{ '--size': '36px', '--color': '#52c41a' }} />
          <span className="text-sm text-gray-500 mt-4">加载中...</span>
        </div>
      </div>
    );
  }

  const color = data.screen1_card.color || '#52c41a';

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <GreenNavBar back={() => router.push('/tcm')}>体质分析报告</GreenNavBar>

      {/* ─────── 第一屏：体质名片 ─────── */}
      <section
        className="px-4 pt-5 pb-6"
        style={{
          background: `linear-gradient(180deg, ${color}15 0%, #fff 100%)`,
        }}
      >
        <div
          className="rounded-2xl p-5 text-center shadow-sm"
          style={{ background: '#fff', border: `1px solid ${color}30` }}
        >
          <div className="text-6xl mb-2">{data.screen1_card.persona.emoji || '🌿'}</div>
          <div className="text-2xl font-bold mb-1" style={{ color }}>
            {data.screen1_card.type}
          </div>
          <div className="text-xs text-gray-500 mb-2">
            为「{data.member_label}」分析 · {new Date(data.created_at).toLocaleDateString()}
          </div>
          <div
            className="inline-block px-3 py-1 rounded-full text-xs mb-4"
            style={{ background: `${color}15`, color }}
          >
            {data.screen1_card.one_line_desc}
          </div>
          <div className="flex justify-center">
            <RadarChart
              dimensions={data.screen1_card.radar.dimensions}
              scores={data.screen1_card.radar.scores}
              color={color}
              size={260}
            />
          </div>
          <div className="text-[11px] text-gray-400 mt-2">9 维体质倾向得分</div>
        </div>
        <div className="text-center text-xs text-gray-400 mt-3 animate-bounce">
          ↓ 向下滑动查看详细分析
        </div>
      </section>

      {/* ─────── 第二屏：深度解读 ─────── */}
      <section className="px-4 pt-2 pb-4">
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <div className="flex items-center mb-3">
            <span className="text-lg mr-2">🔍</span>
            <span className="font-semibold text-gray-800">深度解读</span>
          </div>
          <div className="text-sm text-gray-500 mb-3 leading-relaxed">
            {data.screen1_card.short_desc}
          </div>

          {data.screen2_analysis.features?.external && (
            <div className="mb-3">
              <div className="text-sm font-medium mb-1" style={{ color }}>外在表现</div>
              <div className="flex flex-wrap gap-1.5">
                {data.screen2_analysis.features.external.map((x, i) => (
                  <span
                    key={i}
                    className="text-xs px-2 py-1 rounded"
                    style={{ background: `${color}12`, color: '#555' }}
                  >
                    {x}
                  </span>
                ))}
              </div>
            </div>
          )}

          {data.screen2_analysis.features?.internal && (
            <div className="mb-3">
              <div className="text-sm font-medium mb-1" style={{ color }}>内在倾向</div>
              <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                {data.screen2_analysis.features.internal.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </div>
          )}

          {data.screen2_analysis.features?.easy_problems && (
            <div className="mb-3">
              <div className="text-sm font-medium mb-1 text-orange-500">易患倾向</div>
              <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                {data.screen2_analysis.features.easy_problems.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </div>
          )}

          {(data.screen2_analysis.causes?.innate || data.screen2_analysis.causes?.acquired) && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-sm font-medium mb-2" style={{ color }}>成因分析</div>
              {data.screen2_analysis.causes.innate && (
                <p className="text-xs text-gray-600 mb-2 leading-relaxed">
                  <strong>先天：</strong>
                  {data.screen2_analysis.causes.innate}
                </p>
              )}
              {data.screen2_analysis.causes.acquired && (
                <p className="text-xs text-gray-600 leading-relaxed">
                  <strong>后天：</strong>
                  {data.screen2_analysis.causes.acquired}
                </p>
              )}
            </div>
          )}
        </div>
      </section>

      {/* ─────── 第三屏：个性化养生方案 ─────── */}
      <section className="px-4 pb-4">
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <div className="flex items-center mb-3">
            <span className="text-lg mr-2">🌱</span>
            <span className="font-semibold text-gray-800">个性化养生方案</span>
          </div>

          {/* 饮食 */}
          <div className="mb-4">
            <div className="text-sm font-medium mb-2" style={{ color }}>🍲 饮食宜忌</div>
            {data.screen3_plan.diet?.good && (
              <div className="mb-2">
                <span className="text-xs text-green-600 font-medium mr-1">✓ 宜食：</span>
                <span className="text-xs text-gray-600">
                  {data.screen3_plan.diet.good.join(' · ')}
                </span>
              </div>
            )}
            {data.screen3_plan.diet?.avoid && (
              <div>
                <span className="text-xs text-red-500 font-medium mr-1">✗ 忌食：</span>
                <span className="text-xs text-gray-600">
                  {data.screen3_plan.diet.avoid.join(' · ')}
                </span>
              </div>
            )}
          </div>

          {/* 作息 */}
          {data.screen3_plan.lifestyle?.length > 0 && (
            <div className="mb-4">
              <div className="text-sm font-medium mb-2" style={{ color }}>🌙 作息建议</div>
              <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                {data.screen3_plan.lifestyle.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </div>
          )}

          {/* 运动 */}
          {data.screen3_plan.exercise?.length > 0 && (
            <div className="mb-4">
              <div className="text-sm font-medium mb-2" style={{ color }}>🏃 运动建议</div>
              <div className="space-y-1.5">
                {data.screen3_plan.exercise.map((x, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between text-xs px-3 py-2 rounded-lg"
                    style={{ background: `${color}08` }}
                  >
                    <span className="text-gray-700 font-medium">{x.name}</span>
                    <span className="text-gray-400 text-[11px]">{x.frequency}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 情志 */}
          {data.screen3_plan.emotion?.length > 0 && (
            <div>
              <div className="text-sm font-medium mb-2" style={{ color }}>🧘 情志调养</div>
              <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                {data.screen3_plan.emotion.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>

      {/* ─────── 第四屏：套餐推荐 ─────── */}
      {data.screen4_packages?.length > 0 && (
        <section className="px-4 pb-4">
          <div className="bg-white rounded-2xl p-4 shadow-sm">
            <div className="flex items-center mb-3">
              <span className="text-lg mr-2">🛒</span>
              <span className="font-semibold text-gray-800">专属膳食套餐推荐</span>
            </div>
            <div className="space-y-3">
              {data.screen4_packages.map((pkg, i) => (
                <div
                  key={i}
                  className="rounded-xl p-3 border border-gray-100 transition-all active:bg-gray-50"
                  style={{ background: '#fafafa' }}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className="w-16 h-16 rounded-lg flex-shrink-0 flex items-center justify-center text-2xl"
                      style={{
                        background: `${pkg.reason_tag_color || color}15`,
                        border: `1px solid ${pkg.reason_tag_color || color}30`,
                      }}
                    >
                      {pkg.image ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={pkg.image}
                          alt={pkg.name}
                          className="w-full h-full rounded-lg object-cover"
                          onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')}
                        />
                      ) : (
                        <span>🍲</span>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm mb-0.5 truncate">{pkg.name}</div>
                      <div
                        className="inline-block px-1.5 py-0.5 rounded text-[10px] mb-1"
                        style={{
                          background: `${pkg.reason_tag_color || color}15`,
                          color: pkg.reason_tag_color || color,
                        }}
                      >
                        {pkg.reason}
                      </div>
                      {pkg.matched && pkg.price !== null && (
                        <div className="text-[13px]">
                          <span className="font-bold" style={{ color: '#ff4d4f' }}>
                            ¥{pkg.price}
                          </span>
                          {pkg.original_price && pkg.original_price > (pkg.price || 0) && (
                            <span className="text-gray-300 line-through text-[11px] ml-1.5">
                              ¥{pkg.original_price}
                            </span>
                          )}
                        </div>
                      )}
                      {!pkg.matched && (
                        <div className="text-[11px] text-gray-400">敬请期待</div>
                      )}
                    </div>
                    <Button
                      size="mini"
                      onClick={() => handleBuyPackage(pkg)}
                      style={{
                        background: pkg.matched
                          ? `linear-gradient(135deg, ${color}, #13c2c2)`
                          : '#d9d9d9',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 16,
                        fontSize: 12,
                        padding: '4px 14px',
                      }}
                    >
                      {pkg.matched ? '立即下单' : '暂未上架'}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ─────── 第五屏：广州门店服务 ─────── */}
      <section className="px-4 pb-4">
        <div
          className="rounded-2xl p-4 shadow-sm"
          style={{ background: 'linear-gradient(135deg, #fff7e6, #fffbe6)' }}
        >
          <div className="flex items-center mb-3">
            <span className="text-lg mr-2">🏥</span>
            <span className="font-semibold text-gray-800">广州门店服务</span>
            <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-orange-100 text-orange-600 rounded">
              广州专属
            </span>
          </div>

          {/* 优惠券按钮 */}
          <div
            className="rounded-xl p-3 mb-3 flex items-center gap-3"
            style={{
              background: '#fff',
              border: '1px dashed #faad14',
            }}
          >
            <div className="text-3xl">🎟️</div>
            <div className="flex-1">
              <div className="text-sm font-medium text-gray-800">AI 精准检测体验券</div>
              <div className="text-[11px] text-gray-500 mt-0.5">
                {data.screen5_store.coupon.message}
              </div>
            </div>
            {data.screen5_store.coupon.status === 'claimable' && (
              <Button
                size="small"
                loading={claimingCoupon}
                onClick={handleClaimCoupon}
                style={{
                  background: 'linear-gradient(135deg, #fa8c16, #faad14)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 16,
                  fontSize: 12,
                  padding: '4px 14px',
                }}
              >
                立即领取
              </Button>
            )}
            {data.screen5_store.coupon.status === 'claimed' && (
              <Button
                size="small"
                onClick={handleViewCoupons}
                style={{
                  background: '#f6ffed',
                  color: '#52c41a',
                  border: '1px solid #52c41a',
                  borderRadius: 16,
                  fontSize: 12,
                  padding: '4px 14px',
                }}
              >
                查看我的券
              </Button>
            )}
            {data.screen5_store.coupon.status === 'used' && (
              <span className="text-[11px] text-gray-400">已核销</span>
            )}
          </div>

          {/* 预约艾灸 */}
          <div
            className="rounded-xl p-3 flex items-center gap-3 active:bg-gray-50 cursor-pointer"
            style={{ background: '#fff', border: '1px solid #ffe7ba' }}
            onClick={handleBookAppointment}
          >
            <div className="text-3xl">🔥</div>
            <div className="flex-1">
              <div className="text-sm font-medium text-gray-800">预约艾灸调理</div>
              <div className="text-[11px] text-gray-500 mt-0.5">
                根据您的体质匹配调理方案
              </div>
            </div>
            <span className="text-gray-300">›</span>
          </div>

          <div className="text-[10px] text-gray-400 mt-2 text-center">
            {data.screen5_store.non_guangzhou_fallback_text}
          </div>
        </div>
      </section>

      {/* ─────── 第六屏：分享卡 CTA ─────── */}
      <section className="px-4 pb-6">
        <Button
          block
          onClick={handleShare}
          style={{
            background: `linear-gradient(135deg, ${color}, #13c2c2)`,
            color: '#fff',
            border: 'none',
            borderRadius: 24,
            height: 46,
            fontWeight: 600,
          }}
        >
          📤 生成分享卡，发个朋友圈
        </Button>
        <div className="text-[11px] text-gray-400 mt-3 text-center px-4 leading-relaxed">
          {data.disclaimer}
        </div>
      </section>

      {/* 分享弹窗 */}
      {shareVisible && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-6"
          style={{ background: 'rgba(0,0,0,0.7)' }}
          onClick={() => setShareVisible(false)}
        >
          <div
            className="bg-white rounded-2xl max-h-[90vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-3 text-center text-sm font-semibold border-b">
              长按保存到相册，或点击下方按钮
            </div>
            <div className="p-4 overflow-auto flex items-center justify-center" style={{ minHeight: 360 }}>
              {generatingShare && !shareImageUrl && (
                <SpinLoading style={{ '--size': '36px', '--color': '#52c41a' }} />
              )}
              {shareImageUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={resolveAssetUrl(shareImageUrl)} alt="分享卡" style={{ maxWidth: '100%', maxHeight: '60vh' }} />
              )}
            </div>
            <div className="flex gap-2 p-3 border-t">
              <Button
                block
                onClick={handleSaveShareImage}
                disabled={!shareImageUrl}
                style={{ background: '#52c41a', color: '#fff', border: 'none', borderRadius: 20 }}
              >
                保存图片
              </Button>
              <Button
                block
                onClick={() => setShareVisible(false)}
                style={{ borderRadius: 20 }}
              >
                关闭
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
