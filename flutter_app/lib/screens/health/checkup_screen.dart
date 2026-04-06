import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import '../../providers/health_provider.dart';
import '../../models/checkup_report.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/empty_widget.dart';
import '../../widgets/loading_widget.dart';
import 'report_detail_screen.dart';

class CheckupScreen extends StatefulWidget {
  const CheckupScreen({super.key});

  @override
  State<CheckupScreen> createState() => _CheckupScreenState();
}

class _CheckupScreenState extends State<CheckupScreen> {
  final ImagePicker _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = Provider.of<HealthProvider>(context, listen: false);
      provider.loadReportList();
      provider.loadAlerts();
    });
  }

  Future<void> _refresh() async {
    final provider = Provider.of<HealthProvider>(context, listen: false);
    await Future.wait([
      provider.loadReportList(),
      provider.loadAlerts(),
    ]);
  }

  Future<void> _pickFromGallery() async {
    final image = await _picker.pickImage(source: ImageSource.gallery);
    if (image != null) {
      _handleUpload(image.path);
    }
  }

  Future<void> _pickFromCamera() async {
    final image = await _picker.pickImage(source: ImageSource.camera);
    if (image != null) {
      _handleUpload(image.path);
    }
  }

  Future<void> _pickPdf() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf'],
    );
    if (result != null && result.files.single.path != null) {
      _handleUpload(result.files.single.path!, fileType: 'pdf');
    }
  }

  Future<void> _handleUpload(String filePath, {String fileType = 'image'}) async {
    if (!mounted) return;
    final provider = Provider.of<HealthProvider>(context, listen: false);
    final report = await provider.uploadAndAnalyzeReport(filePath, fileType: fileType);
    if (report != null && mounted) {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ReportDetailScreen(reportId: report.id),
        ),
      );
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('上传或分析失败，请重试')),
      );
    }
  }

  void _navigateToDetail(int reportId) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ReportDetailScreen(reportId: reportId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '体检报告'),
      body: Consumer<HealthProvider>(
        builder: (context, provider, child) {
          if (provider.isUploading) {
            return const LoadingWidget(message: '正在上传并分析报告...');
          }

          return RefreshIndicator(
            onRefresh: _refresh,
            color: const Color(0xFF52C41A),
            child: CustomScrollView(
              slivers: [
                // Alert banner
                if (provider.unreadAlertCount > 0)
                  SliverToBoxAdapter(child: _buildAlertBanner(provider)),

                // Upload section
                SliverToBoxAdapter(child: _buildUploadSection()),

                // History header
                SliverToBoxAdapter(child: _buildHistoryHeader(provider)),

                // Report list
                if (provider.isLoading)
                  const SliverFillRemaining(
                    child: LoadingWidget(message: '加载中...'),
                  )
                else if (provider.reportList.isEmpty)
                  const SliverFillRemaining(
                    child: EmptyWidget(message: '暂无体检报告', icon: Icons.assignment_outlined),
                  )
                else
                  SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (context, index) => _buildReportItem(provider.reportList[index]),
                      childCount: provider.reportList.length,
                    ),
                  ),

                const SliverToBoxAdapter(child: SizedBox(height: 20)),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildAlertBanner(HealthProvider provider) {
    return GestureDetector(
      onTap: () => _showAlertsDialog(provider),
      child: Container(
        margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFFFFF7E6), Color(0xFFFFECD1)],
          ),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFFFD591)),
        ),
        child: Row(
          children: [
            const Icon(Icons.warning_amber_rounded, color: Color(0xFFFA8C16), size: 22),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                '您有 ${provider.unreadAlertCount} 条健康预警未读',
                style: const TextStyle(
                  fontSize: 14,
                  color: Color(0xFFD46B08),
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            const Icon(Icons.chevron_right, color: Color(0xFFFA8C16), size: 20),
          ],
        ),
      ),
    );
  }

  void _showAlertsDialog(HealthProvider provider) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        maxChildSize: 0.85,
        minChildSize: 0.4,
        expand: false,
        builder: (ctx, scrollController) => Column(
          children: [
            const SizedBox(height: 12),
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.grey[300],
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('健康预警', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            ),
            Expanded(
              child: ListView.builder(
                controller: scrollController,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: provider.alerts.length,
                itemBuilder: (ctx, index) {
                  final alert = provider.alerts[index];
                  return Container(
                    margin: const EdgeInsets.only(bottom: 10),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: alert.isRead ? Colors.grey[50] : const Color(0xFFFFF7E6),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: alert.isRead ? Colors.grey[200]! : const Color(0xFFFFD591),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              Icons.circle,
                              size: 8,
                              color: alert.isRead ? Colors.grey : const Color(0xFFFA8C16),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                alert.indicatorName,
                                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                              ),
                            ),
                            Text(
                              alert.createdAt.length >= 10
                                  ? alert.createdAt.substring(0, 10)
                                  : alert.createdAt,
                              style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          alert.alertMessage,
                          style: TextStyle(fontSize: 14, color: Colors.grey[700], height: 1.4),
                        ),
                        if (!alert.isRead) ...[
                          const SizedBox(height: 8),
                          Align(
                            alignment: Alignment.centerRight,
                            child: GestureDetector(
                              onTap: () => provider.markAlertRead(alert.id),
                              child: const Text(
                                '标为已读',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: Color(0xFF52C41A),
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUploadSection() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '上传体检报告',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
          ),
          const SizedBox(height: 4),
          Text(
            'AI智能解读，助您了解健康状况',
            style: TextStyle(fontSize: 13, color: Colors.grey[500]),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: _buildUploadCard(
                icon: Icons.photo_library_outlined,
                label: '从相册选择',
                subtitle: '选取图片',
                color: const Color(0xFF52C41A),
                onTap: _pickFromGallery,
              )),
              const SizedBox(width: 10),
              Expanded(child: _buildUploadCard(
                icon: Icons.camera_alt_outlined,
                label: '拍照上传',
                subtitle: '实时拍摄',
                color: const Color(0xFF1890FF),
                onTap: _pickFromCamera,
              )),
              const SizedBox(width: 10),
              Expanded(child: _buildUploadCard(
                icon: Icons.picture_as_pdf_outlined,
                label: 'PDF文件',
                subtitle: '选取文件',
                color: const Color(0xFFFA541C),
                onTap: _pickPdf,
              )),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildUploadCard({
    required IconData icon,
    required String label,
    required String subtitle,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withOpacity(0.2)),
          boxShadow: [
            BoxShadow(
              color: color.withOpacity(0.06),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(height: 10),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: Colors.grey[800],
              ),
            ),
            const SizedBox(height: 2),
            Text(
              subtitle,
              style: TextStyle(fontSize: 11, color: Colors.grey[400]),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHistoryHeader(HealthProvider provider) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
      child: Row(
        children: [
          const Text(
            '历史报告',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
          ),
          const Spacer(),
          Text(
            '共${provider.reportList.length}份',
            style: TextStyle(fontSize: 13, color: Colors.grey[500]),
          ),
        ],
      ),
    );
  }

  Widget _buildReportItem(CheckupReport report) {
    final statusMap = {
      'pending': {'label': '待分析', 'color': const Color(0xFFFA8C16)},
      'analyzing': {'label': '分析中', 'color': const Color(0xFF1890FF)},
      'completed': {'label': '已完成', 'color': const Color(0xFF52C41A)},
      'failed': {'label': '分析失败', 'color': const Color(0xFFFF4D4F)},
    };
    final statusInfo = statusMap[report.status] ?? statusMap['pending']!;

    return GestureDetector(
      onTap: () => _navigateToDetail(report.id),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.03),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              width: 50,
              height: 50,
              decoration: BoxDecoration(
                color: const Color(0xFF52C41A).withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                report.fileType == 'pdf' ? Icons.picture_as_pdf : Icons.description,
                color: const Color(0xFF52C41A),
                size: 26,
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    report.reportDate != null
                        ? '体检报告 ${report.reportDate}'
                        : '体检报告',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: (statusInfo['color'] as Color).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          statusInfo['label'] as String,
                          style: TextStyle(
                            fontSize: 11,
                            color: statusInfo['color'] as Color,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                      if (report.abnormalCount > 0) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFF4D4F).withOpacity(0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            '${report.abnormalCount}项异常',
                            style: const TextStyle(
                              fontSize: 11,
                              color: Color(0xFFFF4D4F),
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                      const Spacer(),
                      Text(
                        report.createdAt.length >= 10
                            ? report.createdAt.substring(0, 10)
                            : report.createdAt,
                        style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.chevron_right, color: Colors.grey, size: 22),
          ],
        ),
      ),
    );
  }
}
