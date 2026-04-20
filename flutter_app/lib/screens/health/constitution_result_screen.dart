import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';

/// 体质测评 6 屏结果页（一期）
///
/// 接口：`GET /api/constitution/result/{diagnosisId}`
class ConstitutionResultScreen extends StatefulWidget {
  final int diagnosisId;
  const ConstitutionResultScreen({super.key, required this.diagnosisId});

  @override
  State<ConstitutionResultScreen> createState() => _ConstitutionResultScreenState();
}

class _ConstitutionResultScreenState extends State<ConstitutionResultScreen> {
  final ApiService _api = ApiService();
  Map<String, dynamic>? _data;
  bool _loading = true;
  bool _claimingCoupon = false;

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  Color _parseColor(String? hex, {Color fallback = const Color(0xFF52C41A)}) {
    if (hex == null || !hex.startsWith('#') || hex.length < 7) return fallback;
    try {
      final v = int.parse('FF${hex.substring(1)}', radix: 16);
      return Color(v);
    } catch (_) {
      return fallback;
    }
  }

  Future<void> _fetchData() async {
    setState(() => _loading = true);
    try {
      final res = await _api.getConstitutionResult(widget.diagnosisId);
      final data = res.data is Map
          ? Map<String, dynamic>.from((res.data as Map)['data'] ?? res.data)
          : null;
      if (!mounted) return;
      setState(() {
        _data = data;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _loading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('加载结果失败，请稍后重试')),
      );
    }
  }

  Future<void> _claimCoupon() async {
    if (_claimingCoupon) return;
    setState(() => _claimingCoupon = true);
    try {
      final res = await _api.claimConstitutionCoupon();
      final body = res.data is Map ? res.data as Map : {};
      final success = body['success'] == true;
      final already = body['already_claimed'] == true;
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(success ? (already ? '您已领取过该券' : '领取成功，请到「我的优惠券」查看') : '领取失败')),
      );
      if (success) await _fetchData();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('领取失败，请稍后重试')),
      );
    } finally {
      if (mounted) setState(() => _claimingCoupon = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F5F5),
      appBar: const CustomAppBar(title: '体质分析报告'),
      body: _loading || _data == null
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
          : _buildContent(),
    );
  }

  Widget _buildContent() {
    final d = _data!;
    final card = d['screen1_card'] as Map? ?? {};
    final color = _parseColor(card['color'] as String?);
    final persona = card['persona'] as Map? ?? {};

    return SingleChildScrollView(
      padding: const EdgeInsets.only(bottom: 40),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildScreen1(d, color, card, persona),
          const SizedBox(height: 12),
          _buildScreen2(d, color),
          const SizedBox(height: 12),
          _buildScreen3(d, color),
          const SizedBox(height: 12),
          _buildScreen4(d, color),
          const SizedBox(height: 12),
          _buildScreen5(d),
          const SizedBox(height: 12),
          _buildScreen6(d, color),
        ],
      ),
    );
  }

  // ─────────── 屏 1：体质名片 ───────────
  Widget _buildScreen1(Map d, Color color, Map card, Map persona) {
    final radar = card['radar'] as Map? ?? {'dimensions': [], 'scores': []};
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [color.withOpacity(0.12), Colors.white],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Column(
        children: [
          Text(persona['emoji']?.toString() ?? '🌿', style: const TextStyle(fontSize: 72)),
          Text(card['type']?.toString() ?? '—',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: color)),
          const SizedBox(height: 4),
          Text('为「${d['member_label'] ?? '本人'}」分析',
              style: TextStyle(fontSize: 12, color: Colors.grey[500])),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(card['one_line_desc']?.toString() ?? '',
                style: TextStyle(fontSize: 12, color: color)),
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 260,
            child: CustomPaint(
              painter: _RadarPainter(
                dimensions: List<String>.from(radar['dimensions'] ?? []),
                scores: List<num>.from(radar['scores'] ?? []).map((e) => e.toDouble()).toList(),
                color: color,
              ),
              size: const Size.fromHeight(260),
            ),
          ),
          const SizedBox(height: 4),
          Text('9 维体质倾向得分',
              style: TextStyle(fontSize: 11, color: Colors.grey[400])),
        ],
      ),
    );
  }

  // ─────────── 屏 2：深度解读 ───────────
  Widget _buildScreen2(Map d, Color color) {
    final a = d['screen2_analysis'] as Map? ?? {};
    final features = a['features'] as Map? ?? {};
    final causes = a['causes'] as Map? ?? {};

    return _sectionCard(
      title: '🔍 深度解读',
      children: [
        Text(d['screen1_card']?['short_desc']?.toString() ?? '',
            style: TextStyle(fontSize: 13, color: Colors.grey[700], height: 1.6)),
        if (features['external'] is List && (features['external'] as List).isNotEmpty) ...[
          const SizedBox(height: 14),
          _subTitle('外在表现', color),
          Wrap(
            spacing: 6, runSpacing: 6,
            children: (features['external'] as List)
                .map((e) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: color.withOpacity(0.08),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(e.toString(),
                          style: const TextStyle(fontSize: 12, color: Color(0xFF555555))),
                    ))
                .toList(),
          ),
        ],
        if (features['internal'] is List && (features['internal'] as List).isNotEmpty) ...[
          const SizedBox(height: 14),
          _subTitle('内在倾向', color),
          ..._bulletList(features['internal']),
        ],
        if (features['easy_problems'] is List && (features['easy_problems'] as List).isNotEmpty) ...[
          const SizedBox(height: 14),
          _subTitle('易患倾向', const Color(0xFFFA8C16)),
          ..._bulletList(features['easy_problems']),
        ],
        if (causes['innate'] != null || causes['acquired'] != null) ...[
          const SizedBox(height: 14),
          Divider(color: Colors.grey[200], height: 1),
          const SizedBox(height: 14),
          _subTitle('成因分析', color),
          if (causes['innate'] != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: RichText(
                text: TextSpan(
                  style: const TextStyle(fontSize: 12, color: Color(0xFF666666), height: 1.6),
                  children: [
                    const TextSpan(text: '先天：', style: TextStyle(fontWeight: FontWeight.bold)),
                    TextSpan(text: causes['innate'].toString()),
                  ],
                ),
              ),
            ),
          if (causes['acquired'] != null)
            RichText(
              text: TextSpan(
                style: const TextStyle(fontSize: 12, color: Color(0xFF666666), height: 1.6),
                children: [
                  const TextSpan(text: '后天：', style: TextStyle(fontWeight: FontWeight.bold)),
                  TextSpan(text: causes['acquired'].toString()),
                ],
              ),
            ),
        ],
      ],
    );
  }

  // ─────────── 屏 3：个性化方案 ───────────
  Widget _buildScreen3(Map d, Color color) {
    final p = d['screen3_plan'] as Map? ?? {};
    final diet = p['diet'] as Map? ?? {};
    final lifestyle = p['lifestyle'] as List? ?? [];
    final exercise = p['exercise'] as List? ?? [];
    final emotion = p['emotion'] as List? ?? [];

    return _sectionCard(
      title: '🌱 个性化养生方案',
      children: [
        _subTitle('🍲 饮食宜忌', color),
        if (diet['good'] is List)
          _dietLine('✓ 宜食：', const Color(0xFF52C41A),
              (diet['good'] as List).join(' · ')),
        if (diet['avoid'] is List)
          _dietLine('✗ 忌食：', const Color(0xFFFF4D4F),
              (diet['avoid'] as List).join(' · ')),
        if (lifestyle.isNotEmpty) ...[
          const SizedBox(height: 14),
          _subTitle('🌙 作息建议', color),
          ..._bulletList(lifestyle),
        ],
        if (exercise.isNotEmpty) ...[
          const SizedBox(height: 14),
          _subTitle('🏃 运动建议', color),
          ...exercise.map((e) {
            final m = e is Map ? e : {'name': e.toString(), 'frequency': ''};
            return Container(
              margin: const EdgeInsets.only(bottom: 6),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: color.withOpacity(0.05),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(m['name']?.toString() ?? '',
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
                  Text(m['frequency']?.toString() ?? '',
                      style: TextStyle(fontSize: 11, color: Colors.grey[500])),
                ],
              ),
            );
          }),
        ],
        if (emotion.isNotEmpty) ...[
          const SizedBox(height: 14),
          _subTitle('🧘 情志调养', color),
          ..._bulletList(emotion),
        ],
      ],
    );
  }

  // ─────────── 屏 4：套餐推荐 ───────────
  Widget _buildScreen4(Map d, Color color) {
    final pkgs = d['screen4_packages'] as List? ?? [];
    if (pkgs.isEmpty) return const SizedBox.shrink();
    return _sectionCard(
      title: '🛒 专属膳食套餐推荐',
      children: pkgs.map<Widget>((pkgAny) {
        final pkg = pkgAny is Map ? pkgAny : {};
        final matched = pkg['matched'] == true;
        final tagColor = _parseColor(pkg['reason_tag_color']?.toString(), fallback: color);
        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFFFAFAFA),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.grey[200]!),
          ),
          child: Row(
            children: [
              Container(
                width: 56, height: 56,
                decoration: BoxDecoration(
                  color: tagColor.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(8),
                ),
                alignment: Alignment.center,
                child: const Text('🍲', style: TextStyle(fontSize: 28)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(pkg['name']?.toString() ?? '',
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                        maxLines: 1, overflow: TextOverflow.ellipsis),
                    const SizedBox(height: 4),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(
                        color: tagColor.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(pkg['reason']?.toString() ?? '',
                          style: TextStyle(fontSize: 10, color: tagColor)),
                    ),
                    const SizedBox(height: 4),
                    if (matched && pkg['price'] != null)
                      Row(children: [
                        Text('¥${pkg['price']}',
                            style: const TextStyle(
                                fontSize: 14, fontWeight: FontWeight.bold, color: Color(0xFFFF4D4F))),
                        if (pkg['original_price'] != null &&
                            (pkg['original_price'] as num) > (pkg['price'] as num)) ...[
                          const SizedBox(width: 6),
                          Text('¥${pkg['original_price']}',
                              style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.grey[400],
                                  decoration: TextDecoration.lineThrough)),
                        ],
                      ])
                    else if (!matched)
                      Text('敬请期待',
                          style: TextStyle(fontSize: 11, color: Colors.grey[500])),
                  ],
                ),
              ),
              ElevatedButton(
                onPressed: matched
                    ? () => ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('请在商城中查看详情')),
                        )
                    : null,
                style: ElevatedButton.styleFrom(
                  backgroundColor: matched ? color : Colors.grey[300],
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                  minimumSize: Size.zero,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                child: Text(matched ? '下单' : '待上架',
                    style: const TextStyle(fontSize: 12)),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  // ─────────── 屏 5：门店 ───────────
  Widget _buildScreen5(Map d) {
    final s = d['screen5_store'] as Map? ?? {};
    final coupon = s['coupon'] as Map? ?? {};
    final status = coupon['status']?.toString() ?? 'unavailable';
    final message = coupon['message']?.toString() ?? '';

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFF7E6), Color(0xFFFFFBE6)],
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(children: [
            const Text('🏥 广州门店服务',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
              decoration: BoxDecoration(
                color: const Color(0xFFFFF1B8),
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Text('广州专属',
                  style: TextStyle(fontSize: 10, color: Color(0xFFFA8C16))),
            ),
          ]),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFFAAD14), style: BorderStyle.solid),
            ),
            child: Row(
              children: [
                const Text('🎟️', style: TextStyle(fontSize: 32)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('AI 精准检测体验券',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
                      Text(message, style: TextStyle(fontSize: 11, color: Colors.grey[500])),
                    ],
                  ),
                ),
                if (status == 'claimable')
                  ElevatedButton(
                    onPressed: _claimingCoupon ? null : _claimCoupon,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFFA8C16),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                      minimumSize: Size.zero,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    ),
                    child: Text(_claimingCoupon ? '领取中...' : '立即领取',
                        style: const TextStyle(fontSize: 12)),
                  )
                else if (status == 'claimed')
                  OutlinedButton(
                    onPressed: () {},
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF52C41A),
                      side: const BorderSide(color: Color(0xFF52C41A)),
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                      minimumSize: Size.zero,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    ),
                    child: const Text('已领取', style: TextStyle(fontSize: 12)),
                  )
                else if (status == 'used')
                  Text('已核销', style: TextStyle(fontSize: 11, color: Colors.grey[400])),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFFFE7BA)),
            ),
            child: Row(
              children: [
                const Text('🔥', style: TextStyle(fontSize: 32)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('预约艾灸调理',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
                      Text('根据您的体质匹配调理方案',
                          style: TextStyle(fontSize: 11, color: Colors.grey[500])),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: Color(0xFFCCCCCC)),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Text(s['non_guangzhou_fallback_text']?.toString() ?? '',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 10, color: Colors.grey[500])),
        ],
      ),
    );
  }

  // ─────────── 屏 6：分享 ───────────
  Widget _buildScreen6(Map d, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Column(
        children: [
          SizedBox(
            width: double.infinity,
            height: 46,
            child: ElevatedButton(
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('功能开发中，敬请期待')),
                );
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: color,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
              ),
              child: const Text('📤 生成分享卡，发给朋友',
                  style: TextStyle(fontWeight: FontWeight.w600)),
            ),
          ),
          const SizedBox(height: 12),
          Text(d['disclaimer']?.toString() ?? '',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 11, color: Colors.grey[400], height: 1.6)),
        ],
      ),
    );
  }

  // ─────────── 工具方法 ───────────
  Widget _sectionCard({required String title, required List<Widget> children}) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
          const SizedBox(height: 10),
          ...children,
        ],
      ),
    );
  }

  Widget _subTitle(String text, Color color) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Text(text, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: color)),
      );

  List<Widget> _bulletList(dynamic items) {
    if (items is! List) return [];
    return items.map<Widget>((e) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 1),
          child: Text('· ${e.toString()}',
              style: TextStyle(fontSize: 12, color: Colors.grey[700], height: 1.6)),
        )).toList();
  }

  Widget _dietLine(String prefix, Color prefixColor, String content) => Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: RichText(
          text: TextSpan(
            style: const TextStyle(fontSize: 12, color: Color(0xFF666666), height: 1.6),
            children: [
              TextSpan(text: prefix, style: TextStyle(color: prefixColor, fontWeight: FontWeight.w500)),
              TextSpan(text: content),
            ],
          ),
        ),
      );
}

/// 9 维雷达图绘制器
class _RadarPainter extends CustomPainter {
  final List<String> dimensions;
  final List<double> scores;
  final Color color;

  _RadarPainter({required this.dimensions, required this.scores, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    if (dimensions.isEmpty) return;
    final cx = size.width / 2;
    final cy = size.height / 2;
    final r = math.min(size.width, size.height) * 0.38;
    final n = dimensions.length;
    double angle(int i) => math.pi * 2 * i / n - math.pi / 2;

    final bgPaint = Paint()
      ..color = const Color(0xFFE8E8E8)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;

    // 同心多边形
    for (final ratio in [0.25, 0.5, 0.75, 1.0]) {
      final path = Path();
      for (var i = 0; i < n; i++) {
        final x = cx + r * ratio * math.cos(angle(i));
        final y = cy + r * ratio * math.sin(angle(i));
        if (i == 0) {
          path.moveTo(x, y);
        } else {
          path.lineTo(x, y);
        }
      }
      path.close();
      canvas.drawPath(path, bgPaint);
    }

    // 射线
    for (var i = 0; i < n; i++) {
      canvas.drawLine(
        Offset(cx, cy),
        Offset(cx + r * math.cos(angle(i)), cy + r * math.sin(angle(i))),
        bgPaint,
      );
    }

    // 数据多边形
    final dataPath = Path();
    final dataPaintFill = Paint()
      ..color = color.withOpacity(0.25)
      ..style = PaintingStyle.fill;
    final dataPaintStroke = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    final points = <Offset>[];
    for (var i = 0; i < n; i++) {
      final v = i < scores.length ? scores[i].clamp(0, 100) / 100 : 0;
      final x = cx + r * v * math.cos(angle(i));
      final y = cy + r * v * math.sin(angle(i));
      points.add(Offset(x, y));
      if (i == 0) {
        dataPath.moveTo(x, y);
      } else {
        dataPath.lineTo(x, y);
      }
    }
    dataPath.close();
    canvas.drawPath(dataPath, dataPaintFill);
    canvas.drawPath(dataPath, dataPaintStroke);

    // 数据点
    final dotPaint = Paint()..color = color;
    for (final p in points) {
      canvas.drawCircle(p, 3, dotPaint);
    }

    // 标签
    for (var i = 0; i < n; i++) {
      final x = cx + (r + 16) * math.cos(angle(i));
      final y = cy + (r + 16) * math.sin(angle(i));
      final tp = TextPainter(
        text: TextSpan(
          text: dimensions[i],
          style: const TextStyle(fontSize: 11, color: Color(0xFF555555)),
        ),
        textDirection: TextDirection.ltr,
      );
      tp.layout();
      tp.paint(canvas, Offset(x - tp.width / 2, y - tp.height / 2));
    }
  }

  @override
  bool shouldRepaint(covariant _RadarPainter oldDelegate) =>
      oldDelegate.scores != scores || oldDelegate.color != color;
}
