import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';

class DrugScreen extends StatefulWidget {
  const DrugScreen({super.key});

  @override
  State<DrugScreen> createState() => _DrugScreenState();
}

class _DrugScreenState extends State<DrugScreen> {
  final ImagePicker _picker = ImagePicker();
  final ApiService _api = ApiService();

  List<Map<String, dynamic>> _historyList = [];
  bool _isLoadingHistory = true;
  bool _isIdentifying = false;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() => _isLoadingHistory = true);
    try {
      final response = await _api.getDrugIdentifyHistory();
      if (response.statusCode == 200) {
        final data = response.data;
        final rawData = data is Map && data.containsKey('data') ? data['data'] : data;
        final items = rawData is List
            ? rawData
            : (rawData is Map ? (rawData['items'] as List? ?? []) : []);
        setState(() {
          _historyList = items.cast<Map<String, dynamic>>();
        });
      }
    } catch (_) {}
    setState(() => _isLoadingHistory = false);
  }

  Future<void> _pickAndIdentify(ImageSource source) async {
    final image = await _picker.pickImage(source: source);
    if (image == null || !mounted) return;

    setState(() => _isIdentifying = true);
    try {
      final response = await _api.ocrRecognizeDrug(image.path);
      if (!mounted) return;
      setState(() => _isIdentifying = false);

      if (response.statusCode == 200) {
        final data = response.data['data'] ?? response.data;
        final sessionId = data['session_id']?.toString() ?? '';
        if (sessionId.isNotEmpty) {
          Navigator.pushNamed(context, '/drug-chat', arguments: {
            'sessionId': sessionId,
            'drugName': data['drug_name']?.toString() ?? '药品识别',
          });
          _loadHistory();
        } else {
          _showError('识别成功但未获取到会话信息');
        }
      } else {
        _showError('识别失败，请重试');
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _isIdentifying = false);
      _showError('网络异常，请检查网络后重试');
    }
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: Colors.red[400],
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
    );
  }

  String _formatTime(String? timeStr) {
    if (timeStr == null || timeStr.isEmpty) return '';
    try {
      final dt = DateTime.parse(timeStr);
      return '${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return timeStr;
    }
  }

  Widget _buildStatusTag(String? status) {
    Color bgColor;
    Color textColor;
    String label;
    switch (status) {
      case 'completed':
        bgColor = const Color(0xFF52C41A).withOpacity(0.1);
        textColor = const Color(0xFF52C41A);
        label = '已完成';
        break;
      case 'processing':
        bgColor = const Color(0xFF1890FF).withOpacity(0.1);
        textColor = const Color(0xFF1890FF);
        label = '处理中';
        break;
      case 'failed':
        bgColor = Colors.red.withOpacity(0.1);
        textColor = Colors.red;
        label = '失败';
        break;
      default:
        bgColor = const Color(0xFFFA8C16).withOpacity(0.1);
        textColor = const Color(0xFFFA8C16);
        label = status ?? '未知';
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(label, style: TextStyle(fontSize: 11, color: textColor, fontWeight: FontWeight.w500)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '拍照识药'),
      body: Stack(
        children: [
          RefreshIndicator(
            color: const Color(0xFF52C41A),
            onRefresh: _loadHistory,
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildCameraSection(),
                  const SizedBox(height: 16),
                  _buildHistorySection(),
                ],
              ),
            ),
          ),
          if (_isIdentifying) _buildLoadingOverlay(),
        ],
      ),
    );
  }

  Widget _buildCameraSection() {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  const Color(0xFFEB2F96).withOpacity(0.15),
                  const Color(0xFF722ED1).withOpacity(0.15),
                ],
              ),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Icon(Icons.camera_alt, size: 64, color: Color(0xFFEB2F96)),
          ),
          const SizedBox(height: 16),
          const Text(
            '拍摄药品包装，AI帮您解读用药信息',
            style: TextStyle(fontSize: 14, color: Color(0xFF666666), height: 1.5),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          Row(
            children: [
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFFEB2F96), Color(0xFF722ED1)],
                    ),
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: ElevatedButton.icon(
                    onPressed: _isIdentifying ? null : () => _pickAndIdentify(ImageSource.camera),
                    icon: const Icon(Icons.camera_alt, size: 18),
                    label: const Text('拍照识药'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.transparent,
                      shadowColor: Colors.transparent,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _isIdentifying ? null : () => _pickAndIdentify(ImageSource.gallery),
                  icon: const Icon(Icons.photo_library, size: 18),
                  label: const Text('从相册选择'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFFEB2F96),
                    side: const BorderSide(color: Color(0xFFEB2F96)),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHistorySection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                '识别记录',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
              ),
              if (_historyList.isNotEmpty)
                GestureDetector(
                  onTap: _loadHistory,
                  child: Row(
                    children: [
                      Icon(Icons.refresh, size: 16, color: Colors.grey[500]),
                      const SizedBox(width: 4),
                      Text('刷新', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                    ],
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        if (_isLoadingHistory)
          const Padding(
            padding: EdgeInsets.all(40),
            child: Center(child: CircularProgressIndicator(color: Color(0xFF52C41A))),
          )
        else if (_historyList.isEmpty)
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 60),
              child: Column(
                children: [
                  Icon(Icons.medication_outlined, size: 60, color: Colors.grey[300]),
                  const SizedBox(height: 12),
                  Text('暂无识别记录', style: TextStyle(color: Colors.grey[500], fontSize: 15)),
                  const SizedBox(height: 6),
                  Text('拍照识别药品后记录将显示在这里', style: TextStyle(color: Colors.grey[400], fontSize: 13)),
                ],
              ),
            ),
          )
        else
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _historyList.length,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemBuilder: (context, index) => _buildHistoryCard(_historyList[index]),
          ),
        const SizedBox(height: 20),
      ],
    );
  }

  Widget _buildHistoryCard(Map<String, dynamic> item) {
    final drugName = item['drug_name']?.toString() ?? item['title']?.toString() ?? '未知药品';
    final thumbUrl = item['thumbnail']?.toString() ?? item['image_url']?.toString();
    final createdAt = item['created_at']?.toString() ?? item['time']?.toString();
    final status = item['status']?.toString();
    final sessionId = item['session_id']?.toString() ?? '';

    return GestureDetector(
      onTap: () {
        if (sessionId.isNotEmpty) {
          Navigator.pushNamed(context, '/drug-chat', arguments: {
            'sessionId': sessionId,
            'drugName': drugName,
          });
        }
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.03),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: thumbUrl != null && thumbUrl.isNotEmpty
                  ? Image.network(
                      thumbUrl,
                      width: 56,
                      height: 56,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _buildPlaceholderThumb(),
                    )
                  : _buildPlaceholderThumb(),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    drugName,
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _formatTime(createdAt),
                    style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            if (status != null) _buildStatusTag(status),
            const SizedBox(width: 4),
            Icon(Icons.chevron_right, color: Colors.grey[400], size: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildPlaceholderThumb() {
    return Container(
      width: 56,
      height: 56,
      decoration: BoxDecoration(
        color: const Color(0xFFEB2F96).withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Icon(Icons.medication, color: Color(0xFFEB2F96), size: 28),
    );
  }

  Widget _buildLoadingOverlay() {
    return Container(
      color: Colors.black.withOpacity(0.4),
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(color: Color(0xFFEB2F96)),
              const SizedBox(height: 16),
              const Text('正在识别药品...', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              Text('AI正在分析图片，请稍候', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
            ],
          ),
        ),
      ),
    );
  }
}
