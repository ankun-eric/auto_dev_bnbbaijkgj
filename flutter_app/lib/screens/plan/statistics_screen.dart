import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class StatisticsScreen extends StatefulWidget {
  const StatisticsScreen({super.key});

  @override
  State<StatisticsScreen> createState() => _StatisticsScreenState();
}

class _StatisticsScreenState extends State<StatisticsScreen> {
  final ApiService _apiService = ApiService();
  bool _loading = true;
  Map<String, dynamic> _stats = {};

  @override
  void initState() {
    super.initState();
    _loadStatistics();
  }

  Future<void> _loadStatistics() async {
    try {
      final response = await _apiService.getHpStatistics();
      if (response.statusCode == 200 && mounted) {
        final raw = response.data is Map ? response.data as Map<String, dynamic> : <String, dynamic>{};
        setState(() {
          _stats = {
            'today_completed': raw['today_completed'] ?? 0,
            'today_total': raw['today_total'] ?? 0,
            'today_progress': raw['today_progress'] ?? 0,
            'consecutive_days': raw['consecutive_days'] ?? 0,
            'weekly_data': raw['weekly_data'] ?? [],
            'total_checkins': raw['today_completed'] ?? 0,
            'today_checkins': raw['today_completed'] ?? 0,
            'completion_rate': raw['today_progress'] ?? 0,
            'streak_days': raw['consecutive_days'] ?? 0,
          };
          _loading = false;
        });
        return;
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('打卡统计'),
        backgroundColor: const Color(0xFF52C41A),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
          : RefreshIndicator(
              color: const Color(0xFF52C41A),
              onRefresh: _loadStatistics,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildOverviewCard(),
                    const SizedBox(height: 20),
                    _buildStreakCard(),
                    const SizedBox(height: 20),
                    _buildCategoryStats(),
                    const SizedBox(height: 20),
                    _buildWeeklyChart(),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildOverviewCard() {
    final totalCheckins = _stats['total_checkins'] ?? 0;
    final todayCheckins = _stats['today_checkins'] ?? 0;
    final completionRate = (_stats['completion_rate'] ?? 0).toDouble();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('打卡概览', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),
          Row(
            children: [
              _buildStatItem('总打卡', '$totalCheckins', '次'),
              Container(width: 1, height: 40, color: Colors.white.withOpacity(0.3)),
              _buildStatItem('今日打卡', '$todayCheckins', '次'),
              Container(width: 1, height: 40, color: Colors.white.withOpacity(0.3)),
              _buildStatItem('完成率', '${completionRate.toStringAsFixed(0)}', '%'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(String label, String value, String unit) {
    return Expanded(
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(value, style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold)),
              Padding(
                padding: const EdgeInsets.only(bottom: 3),
                child: Text(unit, style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 13)),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(label, style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildStreakCard() {
    final streakDays = _stats['streak_days'] ?? 0;
    final longestStreak = _stats['longest_streak'] ?? 0;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8, offset: const Offset(0, 2))],
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0xFFFA8C16).withOpacity(0.1),
                  ),
                  child: const Icon(Icons.local_fire_department, color: Color(0xFFFA8C16), size: 28),
                ),
                const SizedBox(height: 8),
                Text('$streakDays', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Color(0xFFFA8C16))),
                Text('连续打卡天数', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
              ],
            ),
          ),
          Container(width: 1, height: 80, color: Colors.grey[200]),
          Expanded(
            child: Column(
              children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0xFF722ED1).withOpacity(0.1),
                  ),
                  child: const Icon(Icons.emoji_events, color: Color(0xFF722ED1), size: 28),
                ),
                const SizedBox(height: 8),
                Text('$longestStreak', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Color(0xFF722ED1))),
                Text('最长连续天数', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoryStats() {
    final medCount = _stats['medication_checkins'] ?? 0;
    final checkinCount = _stats['checkin_item_checkins'] ?? 0;
    final planCount = _stats['plan_task_checkins'] ?? 0;

    final categories = [
      {'label': '用药打卡', 'count': medCount, 'color': const Color(0xFFFA8C16), 'icon': Icons.medication},
      {'label': '健康打卡', 'count': checkinCount, 'color': const Color(0xFF52C41A), 'icon': Icons.check_circle_outline},
      {'label': '计划打卡', 'count': planCount, 'color': const Color(0xFF1890FF), 'icon': Icons.flag},
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('分类统计', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
        const SizedBox(height: 12),
        ...categories.map((cat) {
          final color = cat['color'] as Color;
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
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(cat['icon'] as IconData, color: color, size: 22),
                ),
                const SizedBox(width: 14),
                Expanded(child: Text(cat['label'] as String, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500))),
                Text('${cat['count']}', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
                const SizedBox(width: 4),
                Text('次', style: TextStyle(fontSize: 13, color: Colors.grey[400])),
              ],
            ),
          );
        }),
      ],
    );
  }

  Widget _buildWeeklyChart() {
    final weeklyData = _stats['weekly_data'];
    if (weeklyData == null || weeklyData is! List || weeklyData.isEmpty) {
      return const SizedBox.shrink();
    }

    final days = weeklyData.map((d) => Map<String, dynamic>.from(d as Map)).toList();
    final maxVal = days.fold<double>(1, (prev, d) => (d['count'] ?? 0).toDouble() > prev ? (d['count'] ?? 0).toDouble() : prev);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('本周趋势', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
        const SizedBox(height: 12),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: days.map((d) {
              final count = (d['count'] ?? 0).toDouble();
              final ratio = count / maxVal;
              final label = d['day']?.toString() ?? '';
              return Column(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text('${count.toInt()}', style: TextStyle(fontSize: 11, color: Colors.grey[500])),
                  const SizedBox(height: 4),
                  Container(
                    width: 28,
                    height: (ratio * 80).clamp(4, 80),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(4),
                      gradient: LinearGradient(
                        begin: Alignment.bottomCenter,
                        end: Alignment.topCenter,
                        colors: [const Color(0xFF52C41A), const Color(0xFF13C2C2)],
                      ),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(label, style: TextStyle(fontSize: 11, color: Colors.grey[500])),
                ],
              );
            }).toList(),
          ),
        ),
      ],
    );
  }
}
