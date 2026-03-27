import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:image_picker/image_picker.dart';
import '../../providers/health_provider.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/empty_widget.dart';
import '../../widgets/loading_widget.dart';

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
      Provider.of<HealthProvider>(context, listen: false).loadCheckupReports();
    });
  }

  Future<void> _uploadReport() async {
    final image = await _picker.pickImage(source: ImageSource.gallery);
    if (image != null && mounted) {
      final provider = Provider.of<HealthProvider>(context, listen: false);
      final result = await provider.uploadAndAnalyzeCheckup(image.path);
      if (result != null && mounted) {
        _showAnalysisResult(result);
      }
    }
  }

  void _showAnalysisResult(Map<String, dynamic> result) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        maxChildSize: 0.9,
        minChildSize: 0.5,
        expand: false,
        builder: (context, scrollController) => SingleChildScrollView(
          controller: scrollController,
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              const Text(
                'AI分析报告',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: const Color(0xFFF0F9EB),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.check_circle, color: Color(0xFF52C41A), size: 20),
                        SizedBox(width: 8),
                        Text('综合评估', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      result['summary'] ?? '报告分析完成，请查看详细结果。',
                      style: TextStyle(fontSize: 14, color: Colors.grey[700], height: 1.5),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              const Text('建议', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Text(
                result['advice'] ?? '建议定期复查，保持良好的生活习惯。',
                style: TextStyle(fontSize: 14, color: Colors.grey[700], height: 1.6),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '体检报告'),
      body: Consumer<HealthProvider>(
        builder: (context, provider, child) {
          if (provider.isLoading) {
            return const LoadingWidget(message: '加载中...');
          }

          return Column(
            children: [
              GestureDetector(
                onTap: _uploadReport,
                child: Container(
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: const Color(0xFF52C41A).withOpacity(0.3),
                      style: BorderStyle.solid,
                    ),
                  ),
                  child: const Column(
                    children: [
                      Icon(Icons.cloud_upload_outlined, size: 48, color: Color(0xFF52C41A)),
                      SizedBox(height: 12),
                      Text(
                        '上传体检报告',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
                      ),
                      SizedBox(height: 4),
                      Text(
                        '支持拍照或从相册选择，AI智能解读',
                        style: TextStyle(fontSize: 13, color: Color(0xFF999999)),
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  children: [
                    const Text(
                      '历史报告',
                      style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
                    ),
                    const Spacer(),
                    Text('共${provider.checkupReports.length}份',
                        style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: provider.checkupReports.isEmpty
                    ? const EmptyWidget(message: '暂无体检报告', icon: Icons.assignment_outlined)
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        itemCount: provider.checkupReports.length,
                        itemBuilder: (context, index) {
                          final report = provider.checkupReports[index];
                          return Container(
                            margin: const EdgeInsets.only(bottom: 10),
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(
                              children: [
                                Container(
                                  width: 44,
                                  height: 44,
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF52C41A).withOpacity(0.1),
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: const Icon(Icons.description, color: Color(0xFF52C41A)),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        report['name'] ?? '体检报告',
                                        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        report['date'] ?? '',
                                        style: TextStyle(fontSize: 13, color: Colors.grey[500]),
                                      ),
                                    ],
                                  ),
                                ),
                                const Icon(Icons.chevron_right, color: Colors.grey),
                              ],
                            ),
                          );
                        },
                      ),
              ),
            ],
          );
        },
      ),
    );
  }
}
