import 'package:flutter/material.dart';
import '../../widgets/custom_app_bar.dart';

class PointsScreen extends StatefulWidget {
  const PointsScreen({super.key});

  @override
  State<PointsScreen> createState() => _PointsScreenState();
}

class _PointsScreenState extends State<PointsScreen> {
  bool _isCheckedIn = false;

  final List<Map<String, dynamic>> _records = [
    {'title': '每日签到', 'points': '+10', 'date': '2024-03-27', 'isIncome': true},
    {'title': '完成问诊', 'points': '+20', 'date': '2024-03-26', 'isIncome': true},
    {'title': '兑换礼品', 'points': '-200', 'date': '2024-03-25', 'isIncome': false},
    {'title': '健康打卡', 'points': '+5', 'date': '2024-03-24', 'isIncome': true},
    {'title': '分享文章', 'points': '+10', 'date': '2024-03-23', 'isIncome': true},
  ];

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
      body: SingleChildScrollView(
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
                  const Text(
                    '2,580',
                    style: TextStyle(color: Colors.white, fontSize: 40, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton(
                    onPressed: _isCheckedIn
                        ? null
                        : () {
                            setState(() => _isCheckedIn = true);
                          },
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
                  _buildEarnItem(Icons.smart_toy, '问诊', '+20/次'),
                  _buildEarnItem(Icons.share, '分享', '+10/次'),
                  _buildEarnItem(Icons.checklist, '打卡', '+5/次'),
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
            ...List.generate(_records.length, (index) {
              final record = _records[index];
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
                        color: (record['isIncome'] as bool)
                            ? const Color(0xFF52C41A).withOpacity(0.1)
                            : Colors.red.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(
                        (record['isIncome'] as bool) ? Icons.add_circle_outline : Icons.remove_circle_outline,
                        color: (record['isIncome'] as bool) ? const Color(0xFF52C41A) : Colors.red,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(record['title'], style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
                          Text(record['date'], style: TextStyle(fontSize: 12, color: Colors.grey[400])),
                        ],
                      ),
                    ),
                    Text(
                      record['points'],
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: (record['isIncome'] as bool) ? const Color(0xFF52C41A) : Colors.red,
                      ),
                    ),
                  ],
                ),
              );
            }),
            const SizedBox(height: 20),
          ],
        ),
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
