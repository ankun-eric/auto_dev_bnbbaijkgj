import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../config/api_config.dart';
import '../../models/ai_analysis.dart';
import '../../models/checkup_report.dart';
import '../../providers/health_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/loading_widget.dart';
import 'trend_screen.dart';

const kColorAbnormalHigh = Color(0xFFFF4D4F);
const kColorAbnormalLow = Color(0xFFFAAD14);
const kColorNormal = Color(0xFF52C41A);

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
  ReportAnalysisResult? _analysisResult;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadDetail();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadDetail() async {
    setState(() => _isLoading = true);
    final provider = Provider.of<HealthProvider>(context, listen: false);
    final report = await provider.getReportDetail(widget.reportId);
    ReportAnalysisResult? parsed;
    if (report != null) {
      parsed = _parseAnalysis(report);
    }
    if (mounted) {
      setState(() {
        _report = report;
        _analysisResult = parsed;
        _isLoading = false;
      });
    }
  }

  ReportAnalysisResult? _parseAnalysis(CheckupReport report) {
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

  Map<String, List<CheckupIndicator>> _groupByCategory(List<CheckupIndicator> indicators) {
    final map = <String, List<CheckupIndicator>>{};
    for (final item in indicators) {
      final cat = item.category ?? '其他';
      map.putIfAbsent(cat, () => []).add(item);
    }
    return map;
  }

  List<CheckupIndicator> _sortAbnormalFirst(List<CheckupIndicator> indicators) {
    final list = List<CheckupIndicator>.from(indicators);
    list.sort((a, b) {
      if (a.isAbnormal && !b.isAbnormal) return -1;
      if (!a.isAbnormal && b.isAbnormal) return 1;
      return 0;
    });
    return list;
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
      body: _isLoading
          ? const LoadingWidget(message: '加载报告详情...')
          : _report == null
              ? const Center(child: Text('加载失败，请重试'))
              : _buildBody(),
    );
  }

  Widget _buildBody() {
    final report = _report!;
    return Column(
      children: [
        Container(
          color: Colors.white,
          child: TabBar(
            controller: _tabController,
            labelColor: kColorNormal,
            unselectedLabelColor: Colors.grey[600],
            indicatorColor: kColorNormal,
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
              _buildAiTab(report),
              _buildRawTab(report),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildAiTab(CheckupReport report) {
    if (_analysisResult != null) {
      return _buildStructuredAiView(report, _analysisResult!);
    }
    return _buildFallbackAiView(report);
  }

  Widget _buildStructuredAiView(CheckupReport report, ReportAnalysisResult result) {
    final abnormals = result.allAbnormalItems;
    final hasAbnormal = abnormals.isNotEmpty;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildAbnormalSummaryCard(abnormals, hasAbnormal),
        if (abnormals.isNotEmpty) ...[
          const SizedBox(height: 12),
          ...abnormals.map((item) => _buildAbnormalItemCard(item)),
        ],
        const SizedBox(height: 16),
        _buildCategoryExpansionList(result.categories),
        const SizedBox(height: 16),
        _buildSummarySection(result.summary),
        const SizedBox(height: 12),
        _buildDisclaimerSection(),
        const SizedBox(height: 20),
      ],
    );
  }

  Widget _buildAbnormalSummaryCard(List<IndicatorItem> abnormals, bool hasAbnormal) {
    final bgColor = hasAbnormal ? const Color(0xFFFFF0F0) : const Color(0xFFF0FFF4);
    final textColor = hasAbnormal ? kColorAbnormalHigh : kColorNormal;
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
            Text(
              label,
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: textColor,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAbnormalItemCard(IndicatorItem item) {
    final isHigh = item.status == '偏高';
    final statusColor = isHigh ? kColorAbnormalHigh : kColorAbnormalLow;

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
                Expanded(
                  child: Text(
                    item.name,
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    item.status,
                    style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  item.value,
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: statusColor,
                  ),
                ),
                if (item.unit.isNotEmpty) ...[
                  const SizedBox(width: 4),
                  Text(
                    item.unit,
                    style: TextStyle(fontSize: 14, color: Colors.grey[600]),
                  ),
                ],
              ],
            ),
            if (item.reference.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                '参考范围：${item.reference}',
                style: TextStyle(fontSize: 12, color: Colors.grey[500]),
              ),
            ],
            if (item.suggestion != null && item.suggestion!.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFFE6F4FF),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.lightbulb_outline, size: 16, color: Color(0xFF1890FF)),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        item.suggestion!,
                        style: const TextStyle(fontSize: 13, color: Color(0xFF1890FF), height: 1.4),
                      ),
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

  Widget _buildCategoryExpansionList(List<IndicatorCategory> categories) {
    if (categories.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(bottom: 8),
          child: Text(
            '分类详情',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
          ),
        ),
        ...categories.map((cat) => _buildCategoryExpansion(cat)),
      ],
    );
  }

  Widget _buildCategoryExpansion(IndicatorCategory cat) {
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
            Text(
              cat.name,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            ),
            if (abnormalCount > 0) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: kColorAbnormalHigh.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '$abnormalCount项异常',
                  style: const TextStyle(fontSize: 11, color: kColorAbnormalHigh),
                ),
              ),
            ],
          ],
        ),
        children: [
          const Divider(height: 1, indent: 16, endIndent: 16),
          ...cat.items.map((item) => _buildIndicatorRow(item)),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _buildIndicatorRow(IndicatorItem item) {
    Color statusColor;
    if (item.status == '偏高') {
      statusColor = kColorAbnormalHigh;
    } else if (item.status == '偏低') {
      statusColor = kColorAbnormalLow;
    } else {
      statusColor = kColorNormal;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          Expanded(
            flex: 3,
            child: Text(item.name, style: const TextStyle(fontSize: 13)),
          ),
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
          Expanded(
            flex: 2,
            child: Text(
              item.reference,
              style: TextStyle(fontSize: 11, color: Colors.grey[500]),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: statusColor.withOpacity(0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              item.status,
              style: TextStyle(fontSize: 11, color: statusColor, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSummarySection(String summary) {
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
              Icon(Icons.analytics_outlined, color: kColorNormal, size: 20),
              SizedBox(width: 8),
              Text(
                '综合建议',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            summary,
            style: TextStyle(fontSize: 14, color: Colors.grey[800], height: 1.6),
          ),
        ],
      ),
    );
  }

  Widget _buildFallbackAiView(CheckupReport report) {
    final grouped = _groupByCategory(report.indicators);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (grouped.isNotEmpty)
          ...grouped.entries.map((entry) => _buildLegacyCategorySection(entry.key, entry.value)),
        _buildLegacyAssessmentSection(report),
        _buildDisclaimerSection(),
        const SizedBox(height: 20),
      ],
    );
  }

  Widget _buildLegacyCategorySection(String category, List<CheckupIndicator> indicators) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 10, top: 6),
          child: Row(
            children: [
              Container(
                width: 4,
                height: 18,
                decoration: BoxDecoration(
                  color: kColorNormal,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                category,
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
              ),
            ],
          ),
        ),
        ...indicators.map((indicator) => _buildLegacyIndicatorCard(indicator)),
        const SizedBox(height: 8),
      ],
    );
  }

  Widget _buildLegacyIndicatorCard(CheckupIndicator indicator) {
    final isAbnormal = indicator.isAbnormal;
    final statusColor = indicator.status == 'high'
        ? kColorAbnormalHigh
        : indicator.status == 'low'
            ? kColorAbnormalLow
            : kColorNormal;
    final statusLabel = indicator.status == 'high'
        ? '偏高'
        : indicator.status == 'low'
            ? '偏低'
            : '正常';

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: isAbnormal ? Border.all(color: statusColor.withOpacity(0.3)) : null,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.02),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  indicator.indicatorName,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: isAbnormal ? statusColor : const Color(0xFF333333),
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  statusLabel,
                  style: TextStyle(fontSize: 12, color: statusColor, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Text(
                '${indicator.value ?? '-'} ${indicator.unit ?? ''}',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: isAbnormal ? statusColor : const Color(0xFF333333),
                ),
              ),
              const SizedBox(width: 12),
              if (indicator.referenceRange != null)
                Text(
                  '参考: ${indicator.referenceRange}',
                  style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                ),
            ],
          ),
          if (indicator.advice != null && indicator.advice!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F7FA),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.lightbulb_outline, size: 16, color: kColorAbnormalLow),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      indicator.advice!,
                      style: TextStyle(fontSize: 13, color: Colors.grey[700], height: 1.4),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: GestureDetector(
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => TrendScreen(indicatorName: indicator.indicatorName),
                  ),
                );
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: kColorNormal.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.trending_up, size: 16, color: kColorNormal),
                    SizedBox(width: 4),
                    Text(
                      '查看趋势',
                      style: TextStyle(fontSize: 13, color: kColorNormal, fontWeight: FontWeight.w500),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLegacyAssessmentSection(CheckupReport report) {
    final analysisJson = report.aiAnalysisJson;
    final summary = analysisJson?['summary'] ?? report.aiAnalysis ?? '暂无综合评估';
    final advice = analysisJson?['advice'];

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
              Icon(Icons.analytics_outlined, color: kColorNormal, size: 22),
              SizedBox(width: 8),
              Text(
                '综合评估',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            summary.toString(),
            style: TextStyle(fontSize: 14, color: Colors.grey[800], height: 1.6),
          ),
          if (advice != null) ...[
            const SizedBox(height: 12),
            const Text(
              '建议',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
            ),
            const SizedBox(height: 6),
            Text(
              advice.toString(),
              style: TextStyle(fontSize: 14, color: Colors.grey[700], height: 1.6),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildDisclaimerSection() {
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
          const Icon(Icons.warning_amber_rounded, size: 18, color: kColorAbnormalLow),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '免责声明：本解读结果由AI智能分析生成，仅供参考，不构成医疗诊断或治疗建议。如有健康疑问，请及时咨询专业医生。',
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey[700],
                height: 1.5,
                fontStyle: FontStyle.italic,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRawTab(CheckupReport report) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (report.fileUrl != null && report.fileType != 'pdf')
          _buildImagePreview(report),
        if (report.fileType == 'pdf')
          _buildPdfPlaceholder(report),
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
          const Text(
            '原始指标数据',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
          ),
          const SizedBox(height: 8),
          ..._groupByCategory(report.indicators).entries.map(
            (entry) => _buildLegacyCategorySection(entry.key, entry.value),
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
              appBar: AppBar(
                backgroundColor: Colors.black,
                iconTheme: const IconThemeData(color: Colors.white),
                elevation: 0,
              ),
              body: Center(
                child: InteractiveViewer(
                  child: Image.network(
                    report.fileUrl!,
                    fit: BoxFit.contain,
                    errorBuilder: (_, __, ___) => const Icon(
                      Icons.broken_image,
                      color: Colors.white54,
                      size: 64,
                    ),
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
        decoration: BoxDecoration(
          color: Colors.grey[100],
          borderRadius: BorderRadius.circular(12),
        ),
        child: Stack(
          alignment: Alignment.center,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.network(
                report.thumbnailUrl ?? report.fileUrl!,
                fit: BoxFit.cover,
                width: double.infinity,
                errorBuilder: (_, __, ___) => const Icon(
                  Icons.image_not_supported_outlined,
                  size: 48,
                  color: Colors.grey,
                ),
              ),
            ),
            Positioned(
              bottom: 8,
              right: 8,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.black54,
                  borderRadius: BorderRadius.circular(12),
                ),
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

  Widget _buildPdfPlaceholder(CheckupReport report) {
    return Container(
      height: 140,
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(12),
      ),
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
