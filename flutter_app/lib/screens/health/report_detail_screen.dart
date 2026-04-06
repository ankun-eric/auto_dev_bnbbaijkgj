import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../models/checkup_report.dart';
import '../../providers/health_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/loading_widget.dart';
import 'trend_screen.dart';

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
    if (mounted) {
      setState(() {
        _report = report;
        _isLoading = false;
      });
    }
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

  void _showShareDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('分享报告', style: TextStyle(fontSize: 18)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildShareOption(
              icon: Icons.image_outlined,
              label: '生成图片',
              onTap: () {
                Navigator.pop(ctx);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('报告图片已生成')),
                );
              },
            ),
            const Divider(height: 1),
            _buildShareOption(
              icon: Icons.link,
              label: '复制链接',
              onTap: () async {
                Navigator.pop(ctx);
                try {
                  final response = await _api.shareReport(widget.reportId);
                  if (response.statusCode == 200) {
                    final link = response.data['data']?['share_url'] ?? '';
                    if (link.isNotEmpty) {
                      await Clipboard.setData(ClipboardData(text: link));
                    }
                  }
                } catch (_) {}
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('链接已复制到剪贴板')),
                  );
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildShareOption({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return ListTile(
      leading: Icon(icon, color: const Color(0xFF52C41A)),
      title: Text(label),
      onTap: onTap,
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
              onPressed: _showShareDialog,
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
        // Image preview
        if (report.fileUrl != null && report.fileType != 'pdf')
          _buildImagePreview(report),

        // Tab bar
        Container(
          color: Colors.white,
          child: TabBar(
            controller: _tabController,
            labelColor: const Color(0xFF52C41A),
            unselectedLabelColor: Colors.grey[600],
            indicatorColor: const Color(0xFF52C41A),
            indicatorWeight: 3,
            labelStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            tabs: const [
              Tab(text: '分类视图'),
              Tab(text: '异常优先'),
            ],
          ),
        ),

        // Tab content
        Expanded(
          child: TabBarView(
            controller: _tabController,
            children: [
              _buildCategoryView(report),
              _buildAbnormalFirstView(report),
            ],
          ),
        ),
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
        height: 140,
        width: double.infinity,
        color: Colors.grey[100],
        child: Stack(
          alignment: Alignment.center,
          children: [
            Image.network(
              report.thumbnailUrl ?? report.fileUrl!,
              fit: BoxFit.cover,
              width: double.infinity,
              errorBuilder: (_, __, ___) => const Icon(
                Icons.image_not_supported_outlined,
                size: 48,
                color: Colors.grey,
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

  Widget _buildCategoryView(CheckupReport report) {
    final grouped = _groupByCategory(report.indicators);
    if (grouped.isEmpty) {
      return _buildNoIndicatorsView(report);
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ...grouped.entries.map((entry) => _buildCategorySection(entry.key, entry.value)),
        _buildAssessmentSection(report),
        _buildDisclaimerSection(),
        const SizedBox(height: 20),
      ],
    );
  }

  Widget _buildAbnormalFirstView(CheckupReport report) {
    final sorted = _sortAbnormalFirst(report.indicators);
    if (sorted.isEmpty) {
      return _buildNoIndicatorsView(report);
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ...sorted.map((indicator) => _buildIndicatorCard(indicator)),
        _buildAssessmentSection(report),
        _buildDisclaimerSection(),
        const SizedBox(height: 20),
      ],
    );
  }

  Widget _buildNoIndicatorsView(CheckupReport report) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildAssessmentSection(report),
        _buildDisclaimerSection(),
      ],
    );
  }

  Widget _buildCategorySection(String category, List<CheckupIndicator> indicators) {
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
                  color: const Color(0xFF52C41A),
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
        ...indicators.map((indicator) => _buildIndicatorCard(indicator)),
        const SizedBox(height: 8),
      ],
    );
  }

  Widget _buildIndicatorCard(CheckupIndicator indicator) {
    final isAbnormal = indicator.isAbnormal;
    final statusColor = indicator.status == 'high'
        ? const Color(0xFFFF4D4F)
        : indicator.status == 'low'
            ? const Color(0xFFFAAD14)
            : const Color(0xFF52C41A);
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
        border: isAbnormal
            ? Border.all(color: statusColor.withOpacity(0.3))
            : null,
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
                  style: TextStyle(
                    fontSize: 12,
                    color: statusColor,
                    fontWeight: FontWeight.w600,
                  ),
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
                  const Icon(Icons.lightbulb_outline, size: 16, color: Color(0xFFFAAD14)),
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
                  color: const Color(0xFF52C41A).withOpacity(0.08),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.trending_up, size: 16, color: Color(0xFF52C41A)),
                    SizedBox(width: 4),
                    Text(
                      '查看趋势',
                      style: TextStyle(
                        fontSize: 13,
                        color: Color(0xFF52C41A),
                        fontWeight: FontWeight.w500,
                      ),
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

  Widget _buildAssessmentSection(CheckupReport report) {
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
              Icon(Icons.analytics_outlined, color: Color(0xFF52C41A), size: 22),
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
