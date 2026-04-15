import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../config/api_config.dart';
import '../../models/ai_analysis.dart';
import '../../models/checkup_report.dart';
import '../../models/enhanced_report.dart';
import '../../providers/health_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/loading_widget.dart';
import 'report_compare_screen.dart';
import 'trend_screen.dart';

const _kPrimaryGreen = Color(0xFF52C41A);

const _kRiskColors = <int, Color>{
  1: Color(0xFF1B8C3D),
  2: Color(0xFF4CAF50),
  3: Color(0xFFFFC107),
  4: Color(0xFFFF9800),
  5: Color(0xFFF44336),
};

const _kRiskEmojis = <int, String>{
  1: '✅',
  2: '🟢',
  3: '⚠️',
  4: '🔶',
  5: '🔴',
};

Color _scoreColor(double score) {
  if (score >= 90) return const Color(0xFF1B8C3D);
  if (score >= 75) return const Color(0xFF4CAF50);
  if (score >= 60) return const Color(0xFFFFC107);
  if (score >= 40) return const Color(0xFFFF9800);
  return const Color(0xFFF44336);
}

class ReportDetailScreen extends StatefulWidget {
  final int reportId;

  const ReportDetailScreen({super.key, required this.reportId});

  @override
  State<ReportDetailScreen> createState() => _ReportDetailScreenState();
}

class _ReportDetailScreenState extends State<ReportDetailScreen>
    with SingleTickerProviderStateMixin {
  CheckupReport? _report;
  bool _isLoading = true;
  late TabController _tabController;
  final ApiService _api = ApiService();

  EnhancedReportAnalysis? _enhancedAnalysis;
  ReportAnalysisResult? _legacyAnalysis;

  // Progressive loading animation
  bool _isAnalyzing = false;
  double _progress = 0.0;
  String _progressText = '🔍 AI 正在分析您的指标…';
  Timer? _progressTimer;
  Timer? _timeoutTimer;
  bool _isTimedOut = false;
  bool _hasError = false;
  String _errorMessage = '';

  static const _phases = <_ProgressPhase>[
    _ProgressPhase(0.0, 0.30, 2500, '🔍 AI 正在分析您的指标…'),
    _ProgressPhase(0.30, 0.60, 3500, '📊 正在评估各项指标的风险等级…'),
    _ProgressPhase(0.60, 0.90, 6500, '📝 正在生成个性化健康建议…'),
    _ProgressPhase(0.90, 0.99, 50000, '🧠 AI 正在深度分析中，请耐心等待…'),
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadDetail();
  }

  @override
  void dispose() {
    _progressTimer?.cancel();
    _timeoutTimer?.cancel();
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadDetail() async {
    setState(() {
      _isLoading = true;
      _isAnalyzing = true;
      _isTimedOut = false;
      _hasError = false;
      _errorMessage = '';
      _progress = 0.0;
    });
    _startProgressAnimation();
    _startTimeoutTimer();

    try {
      final provider = Provider.of<HealthProvider>(context, listen: false);
      final report = await provider.getReportDetail(widget.reportId);

      EnhancedReportAnalysis? enhanced;
      ReportAnalysisResult? legacy;
      if (report != null) {
        enhanced = _parseEnhancedAnalysis(report);
        if (enhanced == null) {
          legacy = _parseLegacyAnalysis(report);
        }
      }

      _progressTimer?.cancel();
      _timeoutTimer?.cancel();

      if (mounted) {
        if (report == null) {
          setState(() {
            _hasError = true;
            _errorMessage = '加载失败，请重试';
            _isLoading = false;
            _isAnalyzing = false;
          });
          return;
        }
        // Phase 5: animate to 100%
        setState(() {
          _progress = 1.0;
          _progressText = '✅ 分析完成！';
        });
        await Future.delayed(const Duration(milliseconds: 500));
        if (mounted) {
          setState(() {
            _report = report;
            _enhancedAnalysis = enhanced;
            _legacyAnalysis = legacy;
            _isLoading = false;
            _isAnalyzing = false;
          });
        }
      }
    } catch (e) {
      _progressTimer?.cancel();
      _timeoutTimer?.cancel();
      if (mounted) {
        String msg = '分析失败，请重试';
        final eStr = e.toString();
        if (eStr.contains('SocketException') || eStr.contains('Connection')) {
          msg = '网络连接异常，请检查网络后重试';
        } else if (eStr.contains('500')) {
          msg = '服务器繁忙，请稍后重试';
        } else if (eStr.contains('404')) {
          msg = '报告不存在或已被删除';
        }
        setState(() {
          _hasError = true;
          _errorMessage = msg;
          _isLoading = false;
          _isAnalyzing = false;
        });
      }
    }
  }

  void _startProgressAnimation() {
    int phaseIndex = 0;
    final startTime = DateTime.now();

    _progressTimer?.cancel();
    _progressTimer = Timer.periodic(const Duration(milliseconds: 50), (timer) {
      if (!mounted || !_isAnalyzing) {
        timer.cancel();
        return;
      }
      if (phaseIndex >= _phases.length) {
        timer.cancel();
        return;
      }

      final phase = _phases[phaseIndex];
      final elapsed = DateTime.now().difference(startTime).inMilliseconds;

      int phaseStartMs = 0;
      for (int i = 0; i < phaseIndex; i++) {
        phaseStartMs += _phases[i].durationMs;
      }

      final phaseElapsed = elapsed - phaseStartMs;
      final t = (phaseElapsed / phase.durationMs).clamp(0.0, 1.0);
      final eased = _easeOutCubic(t);
      final newProgress = phase.startValue + (phase.endValue - phase.startValue) * eased;

      setState(() {
        _progress = newProgress;
        _progressText = phase.text;
      });

      if (t >= 1.0 && phaseIndex < _phases.length - 1) {
        phaseIndex++;
      }
    });
  }

  double _easeOutCubic(double t) {
    return 1.0 - math.pow(1.0 - t, 3).toDouble();
  }

  void _startTimeoutTimer() {
    _timeoutTimer?.cancel();
    _timeoutTimer = Timer(const Duration(seconds: 60), () {
      if (mounted && _isAnalyzing) {
        _progressTimer?.cancel();
        setState(() {
          _isTimedOut = true;
          _isAnalyzing = false;
          _isLoading = false;
        });
      }
    });
  }

  EnhancedReportAnalysis? _parseEnhancedAnalysis(CheckupReport report) {
    try {
      final raw = report.aiAnalysisJson;
      if (raw != null && raw.containsKey('healthScore') || (raw != null && raw.containsKey('health_score'))) {
        return EnhancedReportAnalysis.fromJson(raw!);
      }
      if (raw != null && raw.containsKey('categories')) {
        final cats = raw['categories'] as List?;
        if (cats != null && cats.isNotEmpty) {
          final first = cats.first;
          if (first is Map && first.containsKey('emoji')) {
            return EnhancedReportAnalysis.fromJson(raw);
          }
        }
      }
    } catch (_) {}
    return null;
  }

  ReportAnalysisResult? _parseLegacyAnalysis(CheckupReport report) {
    try {
      final raw = report.aiAnalysisJson;
      if (raw != null && raw.containsKey('categories')) {
        return ReportAnalysisResult.fromJson(raw);
      }
      final jsonStr = report.aiAnalysis;
      if (jsonStr != null && jsonStr.isNotEmpty) {
        final decoded = jsonDecode(jsonStr);
        if (decoded is Map<String, dynamic>) {
          return ReportAnalysisResult.fromJson(decoded);
        }
      }
    } catch (_) {}
    return null;
  }

  Future<void> _shareReport() async {
    try {
      final response = await _api.shareReport(widget.reportId);
      if (!mounted) return;
      String link = '';
      if (response.statusCode == 200) {
        final d = response.data;
        link = d['data']?['share_url'] ?? d['share_url'] ?? '';
        if (link.isEmpty) {
          final token = d['data']?['share_token'] ?? d['share_token'] ?? '';
          if (token.isNotEmpty) {
            link = '${ApiConfig.baseUrl}/api/report/share/$token';
          }
        }
      }
      if (link.isNotEmpty) {
        await Clipboard.setData(ClipboardData(text: link));
      }
    } catch (_) {}
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('报告链接已复制到剪贴板')),
      );
    }
  }

  void _navigateToCompare() {
    final provider = Provider.of<HealthProvider>(context, listen: false);
    final reports = provider.reportList;
    if (reports.length < 2) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('至少需要两份报告才能进行对比')),
      );
      return;
    }
    final other = reports.firstWhere((r) => r.id != widget.reportId, orElse: () => reports.first);
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ReportCompareScreen(
          reportId1: other.id,
          reportId2: widget.reportId,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: CustomAppBar(
        title: '报告解读',
        actions: [
          if (_report != null)
            IconButton(
              icon: const Icon(Icons.share_outlined, color: Colors.white),
              onPressed: _shareReport,
            ),
        ],
      ),
      body: _buildContent(),
    );
  }

  Widget _buildContent() {
    if (_isTimedOut) {
      return _buildTimeoutView();
    }
    if (_hasError) {
      return _buildErrorView();
    }
    if (_isLoading) {
      return _buildLoadingAnimation();
    }
    if (_report == null) {
      return _buildErrorView();
    }
    return _buildBody();
  }

  Widget _buildLoadingAnimation() {
    final percent = (_progress * 100).toInt();
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 40),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            SizedBox(
              width: 120,
              height: 120,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  SizedBox(
                    width: 120,
                    height: 120,
                    child: CircularProgressIndicator(
                      value: _progress,
                      strokeWidth: 6,
                      backgroundColor: Colors.grey[200],
                      valueColor: const AlwaysStoppedAnimation(_kPrimaryGreen),
                      strokeCap: StrokeCap.round,
                    ),
                  ),
                  Text(
                    '$percent%',
                    style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: _kPrimaryGreen,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 28),
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 400),
              transitionBuilder: (child, animation) => FadeTransition(
                opacity: animation,
                child: SlideTransition(
                  position: Tween<Offset>(
                    begin: const Offset(0, 0.3),
                    end: Offset.zero,
                  ).animate(animation),
                  child: child,
                ),
              ),
              child: Text(
                _progressText,
                key: ValueKey<String>(_progressText),
                style: TextStyle(fontSize: 15, color: Colors.grey[600]),
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTimeoutView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.hourglass_bottom, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 20),
            const Text(
              '分析时间较长，已转入后台处理。\n您可以稍后在报告列表中查看结果。',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 15, color: Color(0xFF666666), height: 1.6),
            ),
            const SizedBox(height: 28),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _kPrimaryGreen,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  elevation: 0,
                ),
                child: const Text('返回报告列表'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorView() {
    final msg = _errorMessage.isNotEmpty ? _errorMessage : '分析失败，请重试';
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.red[300]),
            const SizedBox(height: 20),
            Text(
              msg,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 15, color: Color(0xFF666666), height: 1.6),
            ),
            const SizedBox(height: 28),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _loadDetail,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _kPrimaryGreen,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  elevation: 0,
                ),
                child: const Text('重新分析'),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: () => Navigator.pop(context),
                style: OutlinedButton.styleFrom(
                  foregroundColor: _kPrimaryGreen,
                  side: const BorderSide(color: _kPrimaryGreen),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('返回报告列表'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    return Column(
      children: [
        Container(
          color: Colors.white,
          child: TabBar(
            controller: _tabController,
            labelColor: _kPrimaryGreen,
            unselectedLabelColor: Colors.grey[600],
            indicatorColor: _kPrimaryGreen,
            indicatorWeight: 3,
            labelStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            tabs: const [
              Tab(text: 'AI 解读'),
              Tab(text: '原始报告'),
            ],
          ),
        ),
        Expanded(
          child: TabBarView(
            controller: _tabController,
            children: [
              _buildAiTab(),
              _buildRawTab(),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildAiTab() {
    if (_enhancedAnalysis != null) {
      return _buildEnhancedAiView(_enhancedAnalysis!);
    }
    if (_legacyAnalysis != null) {
      return _buildLegacyAiView(_legacyAnalysis!);
    }
    return _buildFallbackView();
  }

  // ─── Enhanced AI View ────────────────────────────────────────────

  Widget _buildEnhancedAiView(EnhancedReportAnalysis analysis) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (analysis.healthScore != null)
          _buildScoreDashboard(analysis.healthScore!),
        if (analysis.summary != null) ...[
          const SizedBox(height: 16),
          _buildSummaryCards(analysis.summary!),
        ],
        const SizedBox(height: 16),
        _buildEnhancedCategoryList(analysis.categories),
        const SizedBox(height: 16),
        _buildCompareEntryButton(),
        const SizedBox(height: 16),
        _buildDisclaimerSection(analysis.disclaimer),
        const SizedBox(height: 20),
      ],
    );
  }

  // ─── Zone 1: Score Dashboard ─────────────────────────────────────

  Widget _buildScoreDashboard(HealthScoreInfo scoreInfo) {
    final color = _scoreColor(scoreInfo.score);

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [color.withOpacity(0.08), color.withOpacity(0.02)],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Column(
        children: [
          const Text(
            'AI 综合健康评分',
            style: TextStyle(fontSize: 14, color: Color(0xFF666666)),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: 160,
            height: 160,
            child: CustomPaint(
              painter: _ScoreGaugePainter(
                score: scoreInfo.score,
                color: color,
              ),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      scoreInfo.score.toInt().toString(),
                      style: TextStyle(
                        fontSize: 48,
                        fontWeight: FontWeight.bold,
                        color: color,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
                      decoration: BoxDecoration(
                        color: color.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        scoreInfo.level,
                        style: TextStyle(fontSize: 13, color: color, fontWeight: FontWeight.w600),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          if (scoreInfo.comment.isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.auto_awesome, size: 18, color: color),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      scoreInfo.comment,
                      style: TextStyle(fontSize: 14, color: Colors.grey[700], height: 1.5),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _shareReport,
            icon: const Icon(Icons.share_outlined, size: 16),
            label: const Text('分享报告'),
            style: OutlinedButton.styleFrom(
              foregroundColor: color,
              side: BorderSide(color: color.withOpacity(0.4)),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
            ),
          ),
        ],
      ),
    );
  }

  // ─── Zone 2: Summary Cards ───────────────────────────────────────

  Widget _buildSummaryCards(SummaryInfo summary) {
    return Row(
      children: [
        Expanded(child: _statCard('检查项目', '${summary.totalItems}', const Color(0xFF1890FF))),
        const SizedBox(width: 10),
        Expanded(child: _statCard('异常项', '${summary.abnormalCount}', const Color(0xFFF44336))),
        const SizedBox(width: 10),
        Expanded(child: _statCard('优秀项', '${summary.excellentCount}', const Color(0xFF1B8C3D))),
      ],
    );
  }

  Widget _statCard(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.15)),
      ),
      child: Column(
        children: [
          Text(
            value,
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: color),
          ),
          const SizedBox(height: 4),
          Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
        ],
      ),
    );
  }

  // ─── Zone 3: Category Detail List ────────────────────────────────

  Widget _buildEnhancedCategoryList(List<EnhancedCategory> categories) {
    if (categories.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(bottom: 10),
          child: Text(
            '分类指标详细解读',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
          ),
        ),
        ...categories.map((cat) => _buildEnhancedCategoryExpansion(cat)),
      ],
    );
  }

  Widget _buildEnhancedCategoryExpansion(EnhancedCategory cat) {
    final hasAbnormal = cat.abnormalCount > 0;

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: hasAbnormal ? const Color(0xFFF44336).withOpacity(0.2) : Colors.grey[200]!),
      ),
      child: ExpansionTile(
        initiallyExpanded: hasAbnormal,
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        title: Row(
          children: [
            Text(cat.emoji, style: const TextStyle(fontSize: 18)),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                cat.name,
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
              ),
            ),
            if (cat.abnormalCount > 0)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFFF44336).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '${cat.abnormalCount}项异常',
                  style: const TextStyle(fontSize: 11, color: Color(0xFFF44336)),
                ),
              ),
          ],
        ),
        children: [
          const Divider(height: 1, indent: 16, endIndent: 16),
          ...cat.items.map((item) => _buildEnhancedIndicatorCard(item)),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _buildEnhancedIndicatorCard(EnhancedIndicatorItem item) {
    final riskColor = _kRiskColors[item.riskLevel] ?? const Color(0xFF4CAF50);
    final riskEmoji = _kRiskEmojis[item.riskLevel] ?? '🟢';

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: item.isAbnormal ? riskColor.withOpacity(0.04) : Colors.grey[50],
        borderRadius: BorderRadius.circular(10),
        border: item.isAbnormal ? Border.all(color: riskColor.withOpacity(0.2)) : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  item.name,
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                ),
              ),
              Chip(
                label: Text('$riskEmoji ${item.riskName}'),
                labelStyle: TextStyle(fontSize: 11, color: riskColor, fontWeight: FontWeight.w600),
                backgroundColor: riskColor.withOpacity(0.1),
                side: BorderSide(color: riskColor.withOpacity(0.2)),
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                item.value,
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                  color: item.isAbnormal ? riskColor : const Color(0xFF333333),
                ),
              ),
              if (item.unit.isNotEmpty) ...[
                const SizedBox(width: 4),
                Text(item.unit, style: TextStyle(fontSize: 13, color: Colors.grey[600])),
              ],
              const Spacer(),
              if (item.referenceRange.isNotEmpty)
                Text(
                  '参考: ${item.referenceRange}',
                  style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                ),
            ],
          ),
          if (item.detail != null) ...[
            const SizedBox(height: 8),
            _buildDetailAdviceExpansion(item.detail!, item.isAbnormal),
          ],
        ],
      ),
    );
  }

  Widget _buildDetailAdviceExpansion(IndicatorDetailAdvice detail, bool defaultExpanded) {
    final entries = detail.adviceEntries;
    if (entries.isEmpty) return const SizedBox.shrink();

    return ExpansionTile(
      initiallyExpanded: defaultExpanded,
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.zero,
      title: const Text(
        '查看详细建议',
        style: TextStyle(fontSize: 13, color: Color(0xFF1890FF), fontWeight: FontWeight.w500),
      ),
      leading: const Icon(Icons.lightbulb_outline, size: 16, color: Color(0xFF1890FF)),
      children: entries.map((entry) => _buildAdviceModule(entry.key, entry.value)).toList(),
    );
  }

  Widget _buildAdviceModule(String title, String content) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFF5F7FA),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
          ),
          const SizedBox(height: 4),
          Text(
            content,
            style: TextStyle(fontSize: 13, color: Colors.grey[700], height: 1.5),
          ),
        ],
      ),
    );
  }

  // ─── Zone 4: Compare Entry ───────────────────────────────────────

  Widget _buildCompareEntryButton() {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: _navigateToCompare,
        icon: const Icon(Icons.compare_arrows, size: 20),
        label: const Text('与历史报告对比分析'),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF1890FF),
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          elevation: 0,
        ),
      ),
    );
  }

  // ─── Legacy AI View (fallback) ───────────────────────────────────

  Widget _buildLegacyAiView(ReportAnalysisResult result) {
    final abnormals = result.allAbnormalItems;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildLegacyAbnormalSummary(abnormals),
        if (abnormals.isNotEmpty) ...[
          const SizedBox(height: 12),
          ...abnormals.map((item) => _buildLegacyAbnormalCard(item)),
        ],
        const SizedBox(height: 16),
        _buildLegacyCategoryList(result.categories),
        const SizedBox(height: 16),
        _buildLegacySummarySection(result.summary),
        const SizedBox(height: 16),
        _buildCompareEntryButton(),
        const SizedBox(height: 12),
        _buildDisclaimerSection(null),
        const SizedBox(height: 20),
      ],
    );
  }

  Widget _buildLegacyAbnormalSummary(List<IndicatorItem> abnormals) {
    final hasAbnormal = abnormals.isNotEmpty;
    final bgColor = hasAbnormal ? const Color(0xFFFFF0F0) : const Color(0xFFF0FFF4);
    final textColor = hasAbnormal ? const Color(0xFFFF4D4F) : _kPrimaryGreen;
    final icon = hasAbnormal ? Icons.warning_amber_rounded : Icons.check_circle_outline;
    final label = hasAbnormal ? '异常指标（${abnormals.length}项）' : '所有指标正常';

    return Card(
      elevation: 0,
      color: bgColor,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Icon(icon, color: textColor, size: 22),
            const SizedBox(width: 10),
            Text(label, style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: textColor)),
          ],
        ),
      ),
    );
  }

  Widget _buildLegacyAbnormalCard(IndicatorItem item) {
    final isHigh = item.status == '偏高';
    final statusColor = isHigh ? const Color(0xFFFF4D4F) : const Color(0xFFFAAD14);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      shadowColor: Colors.black12,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(item.name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold))),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(color: statusColor, borderRadius: BorderRadius.circular(12)),
                  child: Text(item.status, style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(item.value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: statusColor)),
                if (item.unit.isNotEmpty) ...[
                  const SizedBox(width: 4),
                  Text(item.unit, style: TextStyle(fontSize: 14, color: Colors.grey[600])),
                ],
              ],
            ),
            if (item.reference.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('参考范围：${item.reference}', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
            ],
            if (item.suggestion != null && item.suggestion!.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(color: const Color(0xFFE6F4FF), borderRadius: BorderRadius.circular(8)),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.lightbulb_outline, size: 16, color: Color(0xFF1890FF)),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(item.suggestion!, style: const TextStyle(fontSize: 13, color: Color(0xFF1890FF), height: 1.4)),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildLegacyCategoryList(List<IndicatorCategory> categories) {
    if (categories.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(bottom: 8),
          child: Text('分类详情', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
        ),
        ...categories.map((cat) {
          final abnormalCount = cat.items.where((i) => i.isAbnormal).length;
          return Card(
            margin: const EdgeInsets.only(bottom: 8),
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: Colors.grey[200]!),
            ),
            child: ExpansionTile(
              tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              title: Row(
                children: [
                  Text(cat.name, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                  if (abnormalCount > 0) ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFF4D4F).withOpacity(0.1),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text('$abnormalCount项异常', style: const TextStyle(fontSize: 11, color: Color(0xFFFF4D4F))),
                    ),
                  ],
                ],
              ),
              children: [
                const Divider(height: 1, indent: 16, endIndent: 16),
                ...cat.items.map((item) => _buildLegacyIndicatorRow(item)),
                const SizedBox(height: 8),
              ],
            ),
          );
        }),
      ],
    );
  }

  Widget _buildLegacyIndicatorRow(IndicatorItem item) {
    Color statusColor;
    if (item.status == '偏高' || item.status == 'critical') {
      statusColor = const Color(0xFFFF4D4F);
    } else if (item.status == '偏低' || item.status == 'abnormal') {
      statusColor = const Color(0xFFFAAD14);
    } else {
      statusColor = _kPrimaryGreen;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Expanded(flex: 3, child: Text(item.name, style: const TextStyle(fontSize: 13))),
          Expanded(
            flex: 2,
            child: Text(
              '${item.value} ${item.unit}'.trim(),
              style: TextStyle(
                fontSize: 13,
                fontWeight: item.isAbnormal ? FontWeight.bold : FontWeight.normal,
                color: item.isAbnormal ? statusColor : const Color(0xFF333333),
              ),
            ),
          ),
          Expanded(flex: 2, child: Text(item.reference, style: TextStyle(fontSize: 11, color: Colors.grey[500]))),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(color: statusColor.withOpacity(0.12), borderRadius: BorderRadius.circular(10)),
            child: Text(item.status, style: TextStyle(fontSize: 11, color: statusColor, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }

  Widget _buildLegacySummarySection(String summary) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFF0FFF4),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.analytics_outlined, color: _kPrimaryGreen, size: 20),
              SizedBox(width: 8),
              Text('综合建议', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
            ],
          ),
          const SizedBox(height: 10),
          Text(summary, style: TextStyle(fontSize: 14, color: Colors.grey[800], height: 1.6)),
        ],
      ),
    );
  }

  // ─── Fallback View ───────────────────────────────────────────────

  Widget _buildFallbackView() {
    final report = _report!;
    final grouped = _groupByCategory(report.indicators);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (grouped.isNotEmpty)
          ...grouped.entries.map((entry) => _buildFallbackCategorySection(entry.key, entry.value)),
        _buildFallbackAssessment(report),
        const SizedBox(height: 16),
        _buildCompareEntryButton(),
        _buildDisclaimerSection(null),
        const SizedBox(height: 20),
      ],
    );
  }

  Map<String, List<CheckupIndicator>> _groupByCategory(List<CheckupIndicator> indicators) {
    final map = <String, List<CheckupIndicator>>{};
    for (final item in indicators) {
      map.putIfAbsent(item.category ?? '其他', () => []).add(item);
    }
    return map;
  }

  Widget _buildFallbackCategorySection(String category, List<CheckupIndicator> indicators) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 10, top: 6),
          child: Row(
            children: [
              Container(
                width: 4, height: 18,
                decoration: BoxDecoration(color: _kPrimaryGreen, borderRadius: BorderRadius.circular(2)),
              ),
              const SizedBox(width: 8),
              Text(category, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
            ],
          ),
        ),
        ...indicators.map((ind) => _buildFallbackIndicatorCard(ind)),
        const SizedBox(height: 8),
      ],
    );
  }

  Widget _buildFallbackIndicatorCard(CheckupIndicator indicator) {
    final isAbnormal = indicator.isAbnormal;
    final statusColor = (indicator.status == 'high' || indicator.status == 'critical')
        ? const Color(0xFFFF4D4F)
        : (indicator.status == 'low' || indicator.status == 'abnormal')
            ? const Color(0xFFFAAD14)
            : _kPrimaryGreen;
    final statusLabel = indicator.status == 'high' ? '偏高'
        : indicator.status == 'low' ? '偏低'
        : indicator.status == 'critical' ? '严重异常'
        : indicator.status == 'abnormal' ? '异常'
        : '正常';

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: isAbnormal ? Border.all(color: statusColor.withOpacity(0.3)) : null,
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.02), blurRadius: 6, offset: const Offset(0, 2))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  indicator.indicatorName,
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: isAbnormal ? statusColor : const Color(0xFF333333)),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(color: statusColor.withOpacity(0.1), borderRadius: BorderRadius.circular(12)),
                child: Text(statusLabel, style: TextStyle(fontSize: 12, color: statusColor, fontWeight: FontWeight.w600)),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Text(
                '${indicator.value ?? '-'} ${indicator.unit ?? ''}',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: isAbnormal ? statusColor : const Color(0xFF333333)),
              ),
              const SizedBox(width: 12),
              if (indicator.referenceRange != null)
                Text('参考: ${indicator.referenceRange}', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
            ],
          ),
          if (indicator.advice != null && indicator.advice!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(color: const Color(0xFFF5F7FA), borderRadius: BorderRadius.circular(8)),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.lightbulb_outline, size: 16, color: Color(0xFFFAAD14)),
                  const SizedBox(width: 6),
                  Expanded(child: Text(indicator.advice!, style: TextStyle(fontSize: 13, color: Colors.grey[700], height: 1.4))),
                ],
              ),
            ),
          ],
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: GestureDetector(
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => TrendScreen(indicatorName: indicator.indicatorName))),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(color: _kPrimaryGreen.withOpacity(0.08), borderRadius: BorderRadius.circular(14)),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.trending_up, size: 16, color: _kPrimaryGreen),
                    SizedBox(width: 4),
                    Text('查看趋势', style: TextStyle(fontSize: 13, color: _kPrimaryGreen, fontWeight: FontWeight.w500)),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFallbackAssessment(CheckupReport report) {
    final analysisJson = report.aiAnalysisJson;
    final summary = analysisJson?['summary'] ?? report.aiAnalysis ?? '暂无综合评估';

    return Container(
      margin: const EdgeInsets.only(top: 10, bottom: 10),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFF0F9EB), Color(0xFFE6F7E0)],
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
              Icon(Icons.analytics_outlined, color: _kPrimaryGreen, size: 22),
              SizedBox(width: 8),
              Text('综合评估', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
            ],
          ),
          const SizedBox(height: 12),
          Text(summary.toString(), style: TextStyle(fontSize: 14, color: Colors.grey[800], height: 1.6)),
        ],
      ),
    );
  }

  // ─── Shared Widgets ──────────────────────────────────────────────

  Widget _buildDisclaimerSection(String? disclaimer) {
    final text = disclaimer ?? '本解读结果由AI智能分析生成，仅供参考，不构成医疗诊断或治疗建议。如有健康疑问，请及时咨询专业医生。';

    return Container(
      margin: const EdgeInsets.only(top: 8),
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
              '免责声明：$text',
              style: TextStyle(fontSize: 12, color: Colors.grey[700], height: 1.5, fontStyle: FontStyle.italic),
            ),
          ),
        ],
      ),
    );
  }

  // ─── Raw Tab ─────────────────────────────────────────────────────

  Widget _buildRawTab() {
    final report = _report!;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (report.fileUrl != null && report.fileType != 'pdf')
          _buildImagePreview(report),
        if (report.fileType == 'pdf')
          _buildPdfPlaceholder(),
        if (report.fileUrl == null)
          Center(
            child: Padding(
              padding: const EdgeInsets.all(40),
              child: Column(
                children: [
                  Icon(Icons.description_outlined, size: 60, color: Colors.grey[300]),
                  const SizedBox(height: 12),
                  Text('暂无原始报告文件', style: TextStyle(color: Colors.grey[500])),
                ],
              ),
            ),
          ),
        if (report.indicators.isNotEmpty) ...[
          const SizedBox(height: 16),
          const Text('原始指标数据', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
          const SizedBox(height: 8),
          ..._groupByCategory(report.indicators).entries.map(
            (entry) => _buildFallbackCategorySection(entry.key, entry.value),
          ),
        ],
      ],
    );
  }

  Widget _buildImagePreview(CheckupReport report) {
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => Scaffold(
              backgroundColor: Colors.black,
              appBar: AppBar(backgroundColor: Colors.black, iconTheme: const IconThemeData(color: Colors.white), elevation: 0),
              body: Center(
                child: InteractiveViewer(
                  child: Image.network(
                    report.fileUrl!,
                    fit: BoxFit.contain,
                    errorBuilder: (_, __, ___) => const Icon(Icons.broken_image, color: Colors.white54, size: 64),
                  ),
                ),
              ),
            ),
          ),
        );
      },
      child: Container(
        height: 200,
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 16),
        decoration: BoxDecoration(color: Colors.grey[100], borderRadius: BorderRadius.circular(12)),
        child: Stack(
          alignment: Alignment.center,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.network(
                report.thumbnailUrl ?? report.fileUrl!,
                fit: BoxFit.cover,
                width: double.infinity,
                errorBuilder: (_, __, ___) => const Icon(Icons.image_not_supported_outlined, size: 48, color: Colors.grey),
              ),
            ),
            Positioned(
              bottom: 8,
              right: 8,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(12)),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.zoom_in, color: Colors.white, size: 16),
                    SizedBox(width: 4),
                    Text('点击查看原图', style: TextStyle(color: Colors.white, fontSize: 12)),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPdfPlaceholder() {
    return Container(
      height: 140,
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(color: Colors.grey[100], borderRadius: BorderRadius.circular(12)),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.picture_as_pdf, size: 48, color: Colors.red),
          const SizedBox(height: 8),
          Text('PDF 报告', style: TextStyle(color: Colors.grey[600])),
          const SizedBox(height: 4),
          Text('暂不支持预览，请下载查看', style: TextStyle(color: Colors.grey[400], fontSize: 12)),
        ],
      ),
    );
  }
}

// ─── Score Gauge CustomPainter ──────────────────────────────────────

class _ScoreGaugePainter extends CustomPainter {
  final double score;
  final Color color;

  _ScoreGaugePainter({required this.score, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 8;

    // Background arc
    final bgPaint = Paint()
      ..color = Colors.grey[200]!
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12
      ..strokeCap = StrokeCap.round;

    const startAngle = 0.75 * math.pi;
    const sweepAngle = 1.5 * math.pi;

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepAngle,
      false,
      bgPaint,
    );

    // Score arc
    final scorePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12
      ..strokeCap = StrokeCap.round;

    final scoreSweep = sweepAngle * (score / 100).clamp(0.0, 1.0);

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      scoreSweep,
      false,
      scorePaint,
    );
  }

  @override
  bool shouldRepaint(covariant _ScoreGaugePainter oldDelegate) {
    return oldDelegate.score != score || oldDelegate.color != color;
  }
}

class _ProgressPhase {
  final double startValue;
  final double endValue;
  final int durationMs;
  final String text;

  const _ProgressPhase(this.startValue, this.endValue, this.durationMs, this.text);
}
