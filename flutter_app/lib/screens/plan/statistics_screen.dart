import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
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
          _stats = raw;
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
                    _buildTodayRingCard(),
                    const SizedBox(height: 20),
                    _buildStreakCard(),
                    const SizedBox(height: 20),
                    _buildWeeklyTrendChart(),
                    const SizedBox(height: 20),
                    _buildPlanRankings(),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildTodayRingCard() {
    final todayCompleted = (_stats['today_completed'] ?? 0).toInt();
    final todayTotal = (_stats['today_total'] ?? 0).toInt();
    final progress = (_stats['today_progress'] ?? 0).toDouble();
    final fraction = todayTotal > 0 ? todayCompleted / todayTotal : 0.0;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
        ),
      ),
      child: Column(
        children: [
          const Text('今日完成进度', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 20),
          SizedBox(
            width: 160,
            height: 160,
            child: Stack(
              alignment: Alignment.center,
              children: [
                SizedBox(
                  width: 160,
                  height: 160,
                  child: PieChart(
                    PieChartData(
                      startDegreeOffset: -90,
                      sectionsSpace: 0,
                      centerSpaceRadius: 55,
                      sections: [
                        PieChartSectionData(
                          value: fraction > 0 ? fraction : 0.001,
                          color: Colors.white,
                          radius: 18,
                          showTitle: false,
                        ),
                        PieChartSectionData(
                          value: fraction < 1 ? 1 - fraction : 0.001,
                          color: Colors.white.withOpacity(0.2),
                          radius: 18,
                          showTitle: false,
                        ),
                      ],
                    ),
                  ),
                ),
                Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '${progress.toStringAsFixed(0)}%',
                      style: const TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold),
                    ),
                    Text(
                      '$todayCompleted/$todayTotal',
                      style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 14),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStreakCard() {
    final consecutiveDays = (_stats['consecutive_days'] ?? 0).toInt();
    final streakDays = (_stats['streak_days'] ?? _stats['consecutive_days'] ?? 0).toInt();

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
                Text(
                  '$consecutiveDays',
                  style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Color(0xFFFA8C16)),
                ),
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
                Text(
                  '${math.max(streakDays, consecutiveDays)}',
                  style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Color(0xFF722ED1)),
                ),
                Text('最长连续天数', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWeeklyTrendChart() {
    final weeklyData = _stats['weekly_data'];
    if (weeklyData == null || weeklyData is! List || weeklyData.isEmpty) {
      return const SizedBox.shrink();
    }

    final days = weeklyData.map((d) => Map<String, dynamic>.from(d as Map)).toList();
    final maxVal = days.fold<double>(1, (prev, d) {
      final v = (d['count'] ?? 0).toDouble();
      return v > prev ? v : prev;
    });

    final spots = <FlSpot>[];
    final labels = <String>[];
    for (int i = 0; i < days.length; i++) {
      final count = (days[i]['count'] ?? 0).toDouble();
      spots.add(FlSpot(i.toDouble(), count));
      final dateStr = days[i]['date']?.toString() ?? '';
      labels.add(dateStr.length >= 5 ? dateStr.substring(5) : dateStr);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('本周趋势', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
        const SizedBox(height: 12),
        Container(
          width: double.infinity,
          height: 220,
          padding: const EdgeInsets.fromLTRB(8, 20, 20, 8),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8, offset: const Offset(0, 2))],
          ),
          child: LineChart(
            LineChartData(
              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                horizontalInterval: math.max(1, (maxVal / 4).ceilToDouble()),
                getDrawingHorizontalLine: (value) => FlLine(
                  color: Colors.grey[200]!,
                  strokeWidth: 1,
                ),
              ),
              titlesData: FlTitlesData(
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 32,
                    interval: math.max(1, (maxVal / 4).ceilToDouble()),
                    getTitlesWidget: (value, meta) {
                      return Text(
                        value.toInt().toString(),
                        style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                      );
                    },
                  ),
                ),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 28,
                    interval: 1,
                    getTitlesWidget: (value, meta) {
                      final idx = value.toInt();
                      if (idx < 0 || idx >= labels.length) return const SizedBox.shrink();
                      return Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(labels[idx], style: TextStyle(fontSize: 10, color: Colors.grey[400])),
                      );
                    },
                  ),
                ),
                topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              ),
              borderData: FlBorderData(show: false),
              minX: 0,
              maxX: (days.length - 1).toDouble(),
              minY: 0,
              maxY: maxVal + 1,
              lineBarsData: [
                LineChartBarData(
                  spots: spots,
                  isCurved: true,
                  color: const Color(0xFF52C41A),
                  barWidth: 3,
                  isStrokeCapRound: true,
                  dotData: FlDotData(
                    show: true,
                    getDotPainter: (spot, percent, bar, index) => FlDotCirclePainter(
                      radius: 4,
                      color: Colors.white,
                      strokeWidth: 2,
                      strokeColor: const Color(0xFF52C41A),
                    ),
                  ),
                  belowBarData: BarAreaData(
                    show: true,
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        const Color(0xFF52C41A).withOpacity(0.25),
                        const Color(0xFF52C41A).withOpacity(0.02),
                      ],
                    ),
                  ),
                ),
              ],
              lineTouchData: LineTouchData(
                touchTooltipData: LineTouchTooltipData(
                  getTooltipItems: (touchedSpots) {
                    return touchedSpots.map((s) {
                      return LineTooltipItem(
                        '${s.y.toInt()} 次',
                        const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w500),
                      );
                    }).toList();
                  },
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildPlanRankings() {
    final rankings = _stats['plan_rankings'];
    if (rankings == null || rankings is! List || rankings.isEmpty) {
      return const SizedBox.shrink();
    }

    final items = rankings.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    items.sort((a, b) => ((b['completion_rate'] ?? 0) as num).compareTo((a['completion_rate'] ?? 0) as num));

    final medalColors = [const Color(0xFFFFD700), const Color(0xFFC0C0C0), const Color(0xFFCD7F32)];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('计划完成率排行', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
        const SizedBox(height: 12),
        ...items.asMap().entries.map((entry) {
          final idx = entry.key;
          final item = entry.value;
          final rate = (item['completion_rate'] ?? 0).toDouble();
          final completed = item['completed_count'] ?? 0;
          final total = item['total_count'] ?? 0;
          final planName = item['plan_name']?.toString() ?? '';

          return Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.03), blurRadius: 6, offset: const Offset(0, 2))],
            ),
            child: Row(
              children: [
                if (idx < 3)
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: medalColors[idx].withOpacity(0.15),
                    ),
                    alignment: Alignment.center,
                    child: Icon(Icons.emoji_events, color: medalColors[idx], size: 16),
                  )
                else
                  Container(
                    width: 28,
                    height: 28,
                    alignment: Alignment.center,
                    child: Text('${idx + 1}', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.grey[400])),
                  ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(planName, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
                      const SizedBox(height: 6),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(3),
                        child: LinearProgressIndicator(
                          value: (rate / 100).clamp(0, 1),
                          backgroundColor: const Color(0xFF52C41A).withOpacity(0.1),
                          valueColor: const AlwaysStoppedAnimation(Color(0xFF52C41A)),
                          minHeight: 6,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text('${rate.toStringAsFixed(0)}%', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF52C41A))),
                    Text('$completed/$total', style: TextStyle(fontSize: 11, color: Colors.grey[400])),
                  ],
                ),
              ],
            ),
          );
        }),
      ],
    );
  }
}
