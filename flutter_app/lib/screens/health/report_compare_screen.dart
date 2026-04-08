import 'dart:math' as math;

import 'package:flutter/material.dart';
import '../../models/enhanced_report.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';

const _kPrimaryGreen = Color(0xFF52C41A);

const _kRiskColors = <int, Color>{
  1: Color(0xFF1B8C3D),
  2: Color(0xFF4CAF50),
  3: Color(0xFFFFC107),
  4: Color(0xFFFF9800),
  5: Color(0xFFF44336),
};

Color _scoreColor(double score) {
  if (score >= 90) return const Color(0xFF1B8C3D);
  if (score >= 75) return const Color(0xFF4CAF50);
  if (score >= 60) return const Color(0xFFFFC107);
  if (score >= 40) return const Color(0xFFFF9800);
  return const Color(0xFFF44336);
}

enum _FilterType { all, improved, worsened }

class ReportCompareScreen extends StatefulWidget {
  final int reportId1;
  final int reportId2;

  const ReportCompareScreen({
    super.key,
    required this.reportId1,
    required this.reportId2,
  });

  @override
  State<ReportCompareScreen> createState() => _ReportCompareScreenState();
}

class _ReportCompareScreenState extends State<ReportCompareScreen> {
  final ApiService _api = ApiService();
  ReportCompareResult? _result;
  bool _isLoading = true;
  String? _error;
  _FilterType _filter = _FilterType.all;

  int _loadingTextIndex = 0;
  bool _isAnimating = true;
  static const _loadingTexts = [
    '正在加载两份报告...',
    'AI 正在对比分析指标变化...',
    '正在计算健康评分差异...',
    '正在生成对比建议...',
    '即将完成...',
  ];

  @override
  void initState() {
    super.initState();
    _loadCompare();
  }

  Future<void> _loadCompare() async {
    setState(() {
      _isLoading = true;
      _isAnimating = true;
    });
    _startLoadingAnimation();

    try {
      final response = await _api.compareReports(widget.reportId1, widget.reportId2);
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map<String, dynamic> ? response.data as Map<String, dynamic> : <String, dynamic>{};
        setState(() {
          _result = ReportCompareResult.fromJson(data);
          _isLoading = false;
          _isAnimating = false;
        });
      } else {
        setState(() {
          _error = '加载对比数据失败';
          _isLoading = false;
          _isAnimating = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '加载对比数据失败：$e';
          _isLoading = false;
          _isAnimating = false;
        });
      }
    }
  }

  void _startLoadingAnimation() {
    Future.doWhile(() async {
      await Future.delayed(const Duration(seconds: 2));
      if (!mounted || !_isAnimating) return false;
      setState(() {
        _loadingTextIndex = (_loadingTextIndex + 1) % _loadingTexts.length;
      });
      return _isAnimating;
    });
  }

  List<CompareIndicatorItem> get _filteredIndicators {
    if (_result == null) return [];
    switch (_filter) {
      case _FilterType.all:
        return _result!.indicators;
      case _FilterType.improved:
        return _result!.indicators.where((i) => i.improved).toList();
      case _FilterType.worsened:
        return _result!.indicators.where((i) => i.worsened).toList();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '报告对比分析'),
      body: _isLoading ? _buildLoadingAnimation() : _error != null ? _buildError() : _buildContent(),
    );
  }

  Widget _buildLoadingAnimation() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            width: 80,
            height: 80,
            child: CircularProgressIndicator(
              strokeWidth: 3,
              valueColor: AlwaysStoppedAnimation(_kPrimaryGreen),
            ),
          ),
          const SizedBox(height: 24),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 500),
            transitionBuilder: (child, animation) => FadeTransition(
              opacity: animation,
              child: SlideTransition(
                position: Tween<Offset>(begin: const Offset(0, 0.3), end: Offset.zero).animate(animation),
                child: child,
              ),
            ),
            child: Text(
              _loadingTexts[_loadingTextIndex],
              key: ValueKey<int>(_loadingTextIndex),
              style: TextStyle(fontSize: 15, color: Colors.grey[600]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 48, color: Colors.grey[400]),
          const SizedBox(height: 12),
          Text(_error!, style: TextStyle(color: Colors.grey[600])),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: _loadCompare,
            style: ElevatedButton.styleFrom(backgroundColor: _kPrimaryGreen),
            child: const Text('重试'),
          ),
        ],
      ),
    );
  }

  Widget _buildContent() {
    final result = _result!;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildAiSummary(result.aiSummary),
        if (result.scoreDiff != null) ...[
          const SizedBox(height: 16),
          _buildScoreCompare(result.scoreDiff!),
        ],
        const SizedBox(height: 16),
        _buildFilterButtons(),
        const SizedBox(height: 12),
        _buildIndicatorList(),
        if (result.disclaimer != null && result.disclaimer!.isNotEmpty) ...[
          const SizedBox(height: 16),
          _buildDisclaimer(result.disclaimer!),
        ],
        const SizedBox(height: 20),
      ],
    );
  }

  Widget _buildAiSummary(String summary) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFE6F7FF), Color(0xFFF0FAFF)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF91D5FF)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.auto_awesome, color: Color(0xFF1890FF), size: 20),
              SizedBox(width: 8),
              Text('AI 对比分析总结', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
            ],
          ),
          const SizedBox(height: 12),
          Text(summary, style: TextStyle(fontSize: 14, color: Colors.grey[800], height: 1.6)),
        ],
      ),
    );
  }

  Widget _buildScoreCompare(CompareScoreDiff diff) {
    final prevColor = _scoreColor(diff.previousScore);
    final currColor = _scoreColor(diff.currentScore);
    final isUp = diff.diff > 0;
    final diffColor = isUp ? const Color(0xFF1B8C3D) : (diff.diff < 0 ? const Color(0xFFF44336) : Colors.grey);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 10, offset: const Offset(0, 4))],
      ),
      child: Column(
        children: [
          const Text('健康评分对比', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF333333))),
          const SizedBox(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _miniScoreGauge('上次', diff.previousScore, prevColor),
              Column(
                children: [
                  Icon(
                    isUp ? Icons.arrow_upward : (diff.diff < 0 ? Icons.arrow_downward : Icons.remove),
                    color: diffColor,
                    size: 28,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${isUp ? '+' : ''}${diff.diff.toStringAsFixed(1)}',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: diffColor),
                  ),
                ],
              ),
              _miniScoreGauge('本次', diff.currentScore, currColor),
            ],
          ),
          if (diff.comment.isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: diffColor.withOpacity(0.06),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                diff.comment,
                style: TextStyle(fontSize: 13, color: Colors.grey[700], height: 1.4),
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _miniScoreGauge(String label, double score, Color color) {
    return Column(
      children: [
        SizedBox(
          width: 80,
          height: 80,
          child: CustomPaint(
            painter: _MiniGaugePainter(score: score, color: color),
            child: Center(
              child: Text(
                score.toInt().toString(),
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: color),
              ),
            ),
          ),
        ),
        const SizedBox(height: 6),
        Text(label, style: TextStyle(fontSize: 13, color: Colors.grey[600])),
      ],
    );
  }

  Widget _buildFilterButtons() {
    return Row(
      children: [
        const Text('指标对比', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
        const Spacer(),
        _filterChip('全部', _FilterType.all),
        const SizedBox(width: 6),
        _filterChip('变好', _FilterType.improved, iconColor: const Color(0xFF1B8C3D)),
        const SizedBox(width: 6),
        _filterChip('变差', _FilterType.worsened, iconColor: const Color(0xFFF44336)),
      ],
    );
  }

  Widget _filterChip(String label, _FilterType type, {Color? iconColor}) {
    final isSelected = _filter == type;
    return GestureDetector(
      onTap: () => setState(() => _filter = type),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? _kPrimaryGreen : Colors.grey[100],
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: isSelected ? Colors.white : (iconColor ?? Colors.grey[700]),
          ),
        ),
      ),
    );
  }

  Widget _buildIndicatorList() {
    final items = _filteredIndicators;
    if (items.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(24),
        alignment: Alignment.center,
        child: Text('没有匹配的指标', style: TextStyle(color: Colors.grey[500])),
      );
    }

    return Column(
      children: items.map((item) => _buildCompareIndicatorCard(item)).toList(),
    );
  }

  Widget _buildCompareIndicatorCard(CompareIndicatorItem item) {
    final directionIcon = item.improved
        ? Icons.trending_down
        : item.worsened
            ? Icons.trending_up
            : Icons.trending_flat;
    final directionColor = item.improved
        ? const Color(0xFF1B8C3D)
        : item.worsened
            ? const Color(0xFFF44336)
            : Colors.grey;
    final prevRiskColor = _kRiskColors[item.previousRiskLevel] ?? const Color(0xFF4CAF50);
    final currRiskColor = _kRiskColors[item.currentRiskLevel] ?? const Color(0xFF4CAF50);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey[200]!),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(item.name, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
              ),
              Icon(directionIcon, color: directionColor, size: 22),
              const SizedBox(width: 4),
              Text(
                item.change,
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: directionColor),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _valueColumn(
                  '上次',
                  item.previousValue,
                  item.unit,
                  prevRiskColor,
                ),
              ),
              const Icon(Icons.arrow_forward, size: 16, color: Colors.grey),
              Expanded(
                child: _valueColumn(
                  '本次',
                  item.currentValue,
                  item.unit,
                  currRiskColor,
                ),
              ),
            ],
          ),
          if (item.suggestion.isNotEmpty) ...[
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F7FA),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.lightbulb_outline, size: 15, color: Color(0xFF1890FF)),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      item.suggestion,
                      style: TextStyle(fontSize: 12, color: Colors.grey[700], height: 1.4),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _valueColumn(String label, String value, String unit, Color riskColor) {
    return Column(
      children: [
        Text(label, style: TextStyle(fontSize: 11, color: Colors.grey[500])),
        const SizedBox(height: 4),
        RichText(
          text: TextSpan(
            children: [
              TextSpan(
                text: value,
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: riskColor),
              ),
              if (unit.isNotEmpty)
                TextSpan(
                  text: ' $unit',
                  style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildDisclaimer(String disclaimer) {
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
              '免责声明：$disclaimer',
              style: TextStyle(fontSize: 12, color: Colors.grey[700], height: 1.5, fontStyle: FontStyle.italic),
            ),
          ),
        ],
      ),
    );
  }
}

class _MiniGaugePainter extends CustomPainter {
  final double score;
  final Color color;

  _MiniGaugePainter({required this.score, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 6;

    final bgPaint = Paint()
      ..color = Colors.grey[200]!
      ..style = PaintingStyle.stroke
      ..strokeWidth = 8
      ..strokeCap = StrokeCap.round;

    const startAngle = 0.75 * math.pi;
    const sweepAngle = 1.5 * math.pi;

    canvas.drawArc(Rect.fromCircle(center: center, radius: radius), startAngle, sweepAngle, false, bgPaint);

    final scorePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 8
      ..strokeCap = StrokeCap.round;

    final scoreSweep = sweepAngle * (score / 100).clamp(0.0, 1.0);
    canvas.drawArc(Rect.fromCircle(center: center, radius: radius), startAngle, scoreSweep, false, scorePaint);
  }

  @override
  bool shouldRepaint(covariant _MiniGaugePainter oldDelegate) {
    return oldDelegate.score != score || oldDelegate.color != color;
  }
}
