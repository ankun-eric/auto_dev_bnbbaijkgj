import 'package:flutter/material.dart';
import '../services/api_service.dart';

class CheckinPointsProgress extends StatefulWidget {
  final VoidCallback? onTap;

  const CheckinPointsProgress({super.key, this.onTap});

  @override
  State<CheckinPointsProgress> createState() => CheckinPointsProgressState();
}

class CheckinPointsProgressState extends State<CheckinPointsProgress> {
  final ApiService _apiService = ApiService();
  bool _loading = true;
  bool _enabled = false;
  int _earnedToday = 0;
  int _dailyLimit = 50;
  bool _isLimitReached = false;

  @override
  void initState() {
    super.initState();
    loadProgress();
  }

  Future<void> loadProgress() async {
    final data = await _apiService.getCheckinTodayProgress();
    if (!mounted) return;
    setState(() {
      _enabled = data['enabled'] == true;
      _earnedToday = data['earned_today'] ?? 0;
      _dailyLimit = data['daily_limit'] ?? 50;
      _isLimitReached = data['is_limit_reached'] == true;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const SizedBox(
        height: 60,
        child: Center(child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF52C41A)))),
      );
    }

    if (!_enabled) return const SizedBox.shrink();

    final progress = _dailyLimit > 0 ? (_earnedToday / _dailyLimit).clamp(0.0, 1.0) : 0.0;
    final color = _isLimitReached ? const Color(0xFF52C41A) : const Color(0xFF1890FF);

    return GestureDetector(
      onTap: widget.onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: color.withOpacity(0.06),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.15)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  _isLimitReached ? Icons.emoji_events_rounded : Icons.star_rounded,
                  size: 18,
                  color: color,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    _isLimitReached ? '今日打卡积分已满 \u2713' : '今日打卡积分：$_earnedToday / $_dailyLimit',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: color,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: progress,
                minHeight: 6,
                backgroundColor: color.withOpacity(0.12),
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
