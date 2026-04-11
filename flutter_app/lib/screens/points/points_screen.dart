import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';

class PointsScreen extends StatefulWidget {
  const PointsScreen({super.key});

  @override
  State<PointsScreen> createState() => _PointsScreenState();
}

class _PointsScreenState extends State<PointsScreen> {
  final ApiService _apiService = ApiService();
  bool _isCheckedIn = false;
  bool _loading = true;
  int _points = 0;
  List<Map<String, dynamic>> _records = [];

  static const _typeConfig = <String, Map<String, dynamic>>{
    'signin': {'icon': Icons.check_circle_outline, 'label': '每日签到', 'color': Color(0xFF52C41A)},
    'checkin': {'icon': Icons.fitness_center_rounded, 'label': '健康打卡', 'color': Color(0xFF1890FF)},
    'consultation': {'icon': Icons.smart_toy, 'label': '健康咨询', 'color': Color(0xFF722ED1)},
    'share': {'icon': Icons.share, 'label': '分享', 'color': Color(0xFF13C2C2)},
    'redeem': {'icon': Icons.card_giftcard, 'label': '积分兑换', 'color': Color(0xFFFA541C)},
  };

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      final balanceRes = await _apiService.getPointsBalance();
      final recordsRes = await _apiService.getPointsRecords();
      if (!mounted) return;
      final balanceData = balanceRes.data is Map ? balanceRes.data as Map<String, dynamic> : <String, dynamic>{};
      final recordsData = recordsRes.data is Map ? recordsRes.data as Map<String, dynamic> : <String, dynamic>{};
      final items = recordsData['items'];
      setState(() {
        _points = balanceData['points'] ?? 0;
        _records = (items is List)
            ? items.map((e) => Map<String, dynamic>.from(e as Map)).toList()
            : [];
        _loading = false;
      });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _doSignIn() async {
    try {
      await _apiService.pointsCheckin();
      setState(() => _isCheckedIn = true);
      _loadData();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('签到失败或今日已签到'), backgroundColor: Colors.red),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: CustomAppBar(
        title: '积分中心',
        actions: [
          TextButton(
            onPressed: () => Navigator.pushNamed(context, '/points-mall'),
            child: const Text('积分商城', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
          : RefreshIndicator(
              color: const Color(0xFF52C41A),
              onRefresh: _loadData,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                child: Column(
                  children: [
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(24),
                      decoration: const BoxDecoration(
                        gradient: LinearGradient(
                          colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
                        ),
                      ),
                      child: Column(
                        children: [
                          const Text('当前积分', style: TextStyle(color: Colors.white70, fontSize: 14)),
                          const SizedBox(height: 8),
                          Text(
                            '$_points',
                            style: const TextStyle(color: Colors.white, fontSize: 40, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton(
                            onPressed: _isCheckedIn ? null : _doSignIn,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.white,
                              foregroundColor: const Color(0xFF52C41A),
                              disabledBackgroundColor: Colors.white38,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                              padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 12),
                            ),
                            child: Text(
                              _isCheckedIn ? '今日已签到 +10' : '立即签到 +10',
                              style: const TextStyle(fontWeight: FontWeight.w600),
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      margin: const EdgeInsets.all(16),
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceAround,
                        children: [
                          _buildEarnItem(Icons.check_circle_outline, '签到', '+10/天'),
                          _buildEarnItem(Icons.smart_toy, '咨询', '+20/次'),
                          _buildEarnItem(Icons.share, '分享', '+10/次'),
                          _buildEarnItem(Icons.fitness_center_rounded, '打卡', '+积分'),
                        ],
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text('积分记录', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                          TextButton(
                            onPressed: () {},
                            child: const Text('查看全部', style: TextStyle(color: Color(0xFF52C41A), fontSize: 13)),
                          ),
                        ],
                      ),
                    ),
                    if (_records.isEmpty)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 40),
                        child: Text('暂无积分记录', style: TextStyle(fontSize: 14, color: Colors.grey[400])),
                      )
                    else
                      ...List.generate(_records.length, (index) => _buildRecordCard(_records[index])),
                    const SizedBox(height: 20),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildRecordCard(Map<String, dynamic> record) {
    final type = record['type']?.toString() ?? '';
    final config = _typeConfig[type];
    final pts = record['points'] ?? 0;
    final isIncome = pts > 0;
    final icon = config?['icon'] as IconData? ?? (isIncome ? Icons.add_circle_outline : Icons.remove_circle_outline);
    final color = config?['color'] as Color? ?? (isIncome ? const Color(0xFF52C41A) : Colors.red);
    final title = record['description']?.toString() ?? config?['label']?.toString() ?? type;
    final dateStr = record['created_at']?.toString().split('T').first ?? '';
    final pointsStr = isIncome ? '+$pts' : '$pts';

    final isCheckinType = type == 'checkin';

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
                    ),
                    if (isCheckinType) ...[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                        decoration: BoxDecoration(
                          color: const Color(0xFF1890FF).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text('打卡', style: TextStyle(fontSize: 10, color: Color(0xFF1890FF), fontWeight: FontWeight.w600)),
                      ),
                    ],
                  ],
                ),
                Text(dateStr, style: TextStyle(fontSize: 12, color: Colors.grey[400])),
              ],
            ),
          ),
          Text(
            pointsStr,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: isIncome ? const Color(0xFF52C41A) : Colors.red,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEarnItem(IconData icon, String label, String value) {
    return Column(
      children: [
        Icon(icon, color: const Color(0xFF52C41A), size: 28),
        const SizedBox(height: 6),
        Text(label, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
        Text(value, style: TextStyle(fontSize: 11, color: Colors.grey[500])),
      ],
    );
  }
}
