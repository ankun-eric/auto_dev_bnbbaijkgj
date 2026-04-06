import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../models/checkup_report.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/loading_widget.dart';

class TrendScreen extends StatefulWidget {
  final String indicatorName;

  const TrendScreen({super.key, required this.indicatorName});

  @override
  State<TrendScreen> createState() => _TrendScreenState();
}

class _TrendScreenState extends State<TrendScreen> {
  final ApiService _api = ApiService();
  List<TrendData> _trendData = [];
  String? _analysisText;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadTrend();
  }

  Future<void> _loadTrend() async {
    setState(() => _isLoading = true);
    try {
      final response = await _api.getIndicatorTrend(widget.indicatorName);
      if (response.statusCode == 200) {
        final data = response.data['data'];
        final list = data is List ? data : (data?['items'] as List?) ?? [];
        _trendData = list.map<TrendData>((e) => TrendData.fromJson(e)).toList();

        if (_trendData.isNotEmpty) {
          _loadAnalysis();
        }
      }
    } catch (_) {}
    if (mounted) setState(() => _isLoading = false);
  }

  Future<void> _loadAnalysis() async {
    try {
      final rawData = _trendData.map((e) => e.toJson()).toList();
      final response = await _api.getTrendAnalysis(widget.indicatorName, rawData);
      if (response.statusCode == 200) {
        final analysis = response.data['data'];
        if (mounted) {
          setState(() {
            _analysisText = analysis is String
                ? analysis
                : analysis?['analysis']?.toString() ?? analysis?['summary']?.toString();
          });
        }
      }
    } catch (_) {}
  }

  double? _parseRangeLow(String? range) {
    if (range == null) return null;
    final parts = range.replaceAll(RegExp(r'[^\d.\-~]'), '-').split(RegExp(r'[-~]+'));
    if (parts.isEmpty) return null;
    return double.tryParse(parts.first.trim());
  }

  double? _parseRangeHigh(String? range) {
    if (range == null) return null;
    final parts = range.replaceAll(RegExp(r'[^\d.\-~]'), '-').split(RegExp(r'[-~]+'));
    if (parts.length < 2) return null;
    return double.tryParse(parts.last.trim());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: CustomAppBar(title: '${widget.indicatorName} 趋势'),
      body: _isLoading
          ? const LoadingWidget(message: '加载趋势数据...')
          : _trendData.isEmpty
              ? const Center(child: Text('暂无趋势数据'))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    _buildChartCard(),
                    const SizedBox(height: 16),
                    _buildDataTable(),
                    if (_analysisText != null) ...[
                      const SizedBox(height: 16),
                      _buildAnalysisCard(),
                    ],
                    const SizedBox(height: 16),
                    _buildDisclaimerSection(),
                    const SizedBox(height: 20),
                  ],
                ),
    );
  }

  Widget _buildChartCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.indicatorName,
            style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              _legendDot(const Color(0xFF52C41A), '正常范围'),
              const SizedBox(width: 16),
              _legendDot(const Color(0xFF1890FF), '数值'),
              const SizedBox(width: 16),
              _legendDot(const Color(0xFFFF4D4F), '超标'),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 220,
            child: CustomPaint(
              size: Size.infinite,
              painter: _TrendChartPainter(
                data: _trendData,
                rangeLow: _parseRangeLow(_trendData.first.referenceRange),
                rangeHigh: _parseRangeHigh(_trendData.first.referenceRange),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _legendDot(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
      ],
    );
  }

  Widget _buildDataTable() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('历史数据', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          Table(
            columnWidths: const {
              0: FlexColumnWidth(2),
              1: FlexColumnWidth(1.5),
              2: FlexColumnWidth(2),
            },
            children: [
              TableRow(
                decoration: BoxDecoration(color: Colors.grey[50]),
                children: const [
                  Padding(
                    padding: EdgeInsets.all(8),
                    child: Text('日期', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                  ),
                  Padding(
                    padding: EdgeInsets.all(8),
                    child: Text('数值', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                  ),
                  Padding(
                    padding: EdgeInsets.all(8),
                    child: Text('参考范围', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                  ),
                ],
              ),
              ..._trendData.map((d) {
                final low = _parseRangeLow(d.referenceRange);
                final high = _parseRangeHigh(d.referenceRange);
                final outOfRange = (low != null && d.value < low) || (high != null && d.value > high);
                return TableRow(
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(8),
                      child: Text(d.date, style: const TextStyle(fontSize: 13)),
                    ),
                    Padding(
                      padding: const EdgeInsets.all(8),
                      child: Text(
                        d.value.toStringAsFixed(1),
                        style: TextStyle(
                          fontSize: 13,
                          color: outOfRange ? const Color(0xFFFF4D4F) : const Color(0xFF333333),
                          fontWeight: outOfRange ? FontWeight.bold : FontWeight.normal,
                        ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.all(8),
                      child: Text(
                        d.referenceRange ?? '-',
                        style: TextStyle(fontSize: 13, color: Colors.grey[500]),
                      ),
                    ),
                  ],
                );
              }),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildAnalysisCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFE6F7FF), Color(0xFFF0F9FF)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.auto_awesome, color: Color(0xFF1890FF), size: 20),
              SizedBox(width: 8),
              Text(
                'AI趋势分析',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            _analysisText!,
            style: TextStyle(fontSize: 14, color: Colors.grey[800], height: 1.6),
          ),
        ],
      ),
    );
  }

  Widget _buildDisclaimerSection() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBE6),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFFFE58F)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.warning_amber_rounded, size: 18, color: Color(0xFFFAAD14)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '免责声明：本解读结果由AI智能分析生成，仅供参考，不构成医疗诊断或治疗建议。如有健康疑问，请及时咨询专业医生。',
              style: TextStyle(fontSize: 12, color: Colors.grey[700], height: 1.5),
            ),
          ),
        ],
      ),
    );
  }
}

class _TrendChartPainter extends CustomPainter {
  final List<TrendData> data;
  final double? rangeLow;
  final double? rangeHigh;

  _TrendChartPainter({
    required this.data,
    this.rangeLow,
    this.rangeHigh,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (data.isEmpty) return;

    const double paddingLeft = 44;
    const double paddingRight = 16;
    const double paddingTop = 16;
    const double paddingBottom = 40;

    final chartWidth = size.width - paddingLeft - paddingRight;
    final chartHeight = size.height - paddingTop - paddingBottom;

    final values = data.map((d) => d.value).toList();
    double minVal = values.reduce(math.min);
    double maxVal = values.reduce(math.max);

    if (rangeLow != null) minVal = math.min(minVal, rangeLow!);
    if (rangeHigh != null) maxVal = math.max(maxVal, rangeHigh!);

    final valueRange = maxVal - minVal;
    final padding = valueRange * 0.15;
    minVal -= padding;
    maxVal += padding;
    final totalRange = maxVal - minVal;

    double mapY(double v) {
      if (totalRange == 0) return paddingTop + chartHeight / 2;
      return paddingTop + chartHeight * (1 - (v - minVal) / totalRange);
    }

    double mapX(int i) {
      if (data.length == 1) return paddingLeft + chartWidth / 2;
      return paddingLeft + chartWidth * i / (data.length - 1);
    }

    // Normal range band
    if (rangeLow != null && rangeHigh != null) {
      final rangePaint = Paint()
        ..color = const Color(0xFF52C41A).withOpacity(0.10)
        ..style = PaintingStyle.fill;
      final rl = mapY(rangeHigh!);
      final rh = mapY(rangeLow!);
      canvas.drawRect(
        Rect.fromLTRB(paddingLeft, rl, paddingLeft + chartWidth, rh),
        rangePaint,
      );

      final borderPaint = Paint()
        ..color = const Color(0xFF52C41A).withOpacity(0.30)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1;
      canvas.drawLine(Offset(paddingLeft, rl), Offset(paddingLeft + chartWidth, rl), borderPaint);
      canvas.drawLine(Offset(paddingLeft, rh), Offset(paddingLeft + chartWidth, rh), borderPaint);
    }

    // Grid lines
    final gridPaint = Paint()
      ..color = Colors.grey.withOpacity(0.15)
      ..strokeWidth = 0.5;
    const gridCount = 4;
    for (int i = 0; i <= gridCount; i++) {
      final y = paddingTop + chartHeight * i / gridCount;
      canvas.drawLine(Offset(paddingLeft, y), Offset(paddingLeft + chartWidth, y), gridPaint);
      final val = maxVal - totalRange * i / gridCount;
      _drawText(canvas, val.toStringAsFixed(1), Offset(0, y - 7), 10, Colors.grey);
    }

    // Line & points
    final linePaint = Paint()
      ..color = const Color(0xFF1890FF)
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final path = Path();
    final points = <Offset>[];
    for (int i = 0; i < data.length; i++) {
      final x = mapX(i);
      final y = mapY(data[i].value);
      points.add(Offset(x, y));
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, linePaint);

    // Points
    for (int i = 0; i < points.length; i++) {
      final v = data[i].value;
      final outOfRange = (rangeLow != null && v < rangeLow!) || (rangeHigh != null && v > rangeHigh!);
      final pointColor = outOfRange ? const Color(0xFFFF4D4F) : const Color(0xFF1890FF);

      canvas.drawCircle(points[i], 5, Paint()..color = Colors.white);
      canvas.drawCircle(points[i], 4, Paint()..color = pointColor);

      // X-axis label (date)
      final label = data[i].date.length >= 5 ? data[i].date.substring(5) : data[i].date;
      _drawText(
        canvas,
        label,
        Offset(points[i].dx - 20, size.height - paddingBottom + 8),
        10,
        Colors.grey[600]!,
      );
    }
  }

  void _drawText(Canvas canvas, String text, Offset offset, double fontSize, Color color) {
    final textPainter = TextPainter(
      text: TextSpan(text: text, style: TextStyle(fontSize: fontSize, color: color)),
      textDirection: TextDirection.ltr,
    )..layout();
    textPainter.paint(canvas, offset);
  }

  @override
  bool shouldRepaint(covariant _TrendChartPainter oldDelegate) {
    return oldDelegate.data != data ||
        oldDelegate.rangeLow != rangeLow ||
        oldDelegate.rangeHigh != rangeHigh;
  }
}
