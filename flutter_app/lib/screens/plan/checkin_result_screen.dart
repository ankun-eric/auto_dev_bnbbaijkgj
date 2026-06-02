// [PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] 打卡成果页
import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class CheckinResultScreen extends StatefulWidget {
  const CheckinResultScreen({super.key});

  @override
  State<CheckinResultScreen> createState() => _CheckinResultScreenState();
}

class _CheckinResultScreenState extends State<CheckinResultScreen> {
  final ApiService _api = ApiService();
  bool _loading = true;
  Map<String, dynamic> _summary = {
    'streak_days': 0,
    'total_checkins': 0,
    'overall_completion_rate': 0,
    'plans': [],
  };
  List<Map<String, dynamic>> _items = [];
  late int _year;
  late int _month;
  Map<String, int> _calendarMap = {};

  static const _rankColors = [
    Color(0xFF6366F1),
    Color(0xFF8B5CF6),
    Color(0xFFA855F7),
    Color(0xFFEC4899),
    Color(0xFF0EA5E9),
    Color(0xFF10B981),
    Color(0xFFF59E0B),
  ];

  @override
  void initState() {
    super.initState();
    final n = DateTime.now();
    _year = n.year;
    _month = n.month;
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final res = await Future.wait([
        _api.getCheckinStatsSummary(),
        _api.getCheckinItems(),
        _api.getCheckinCalendar(_year, _month),
      ]);
      _summary = res[0].data is Map ? Map<String, dynamic>.from(res[0].data as Map) : _summary;
      final list = (res[1].data is Map ? (res[1].data['items'] as List?) ?? [] : []);
      _items = list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
      final calDays = (res[2].data is Map ? (res[2].data['days'] as List?) ?? [] : []);
      _calendarMap = {
        for (final d in calDays) (d['date'] as String): (d['count'] as int? ?? 0)
      };
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _changeMonth(int delta) async {
    int y = _year;
    int m = _month + delta;
    if (m < 1) { m = 12; y -= 1; }
    if (m > 12) { m = 1; y += 1; }
    final now = DateTime.now();
    if (y > now.year || (y == now.year && m > now.month)) return;
    setState(() { _year = y; _month = m; });
    try {
      final res = await _api.getCheckinCalendar(_year, _month);
      final calDays = (res.data is Map ? (res.data['days'] as List?) ?? [] : []);
      setState(() {
        _calendarMap = {
          for (final d in calDays) (d['date'] as String): (d['count'] as int? ?? 0)
        };
      });
    } catch (_) {}
  }

  String _pad(int n) => n.toString().padLeft(2, '0');

  Future<void> _onDayTap(String dateStr, int count) async {
    final now = DateTime.now();
    final todayStr = '${now.year}-${_pad(now.month)}-${_pad(now.day)}';
    if (dateStr == todayStr) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('请到主页执行今日打卡')));
      return;
    }
    if (count > 0) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('这天已有 $count 次打卡')));
      return;
    }
    final d = DateTime.parse(dateStr);
    final diff = DateTime(now.year, now.month, now.day).difference(d).inDays;
    if (diff < 1 || diff > 3) return;
    if (_items.isEmpty) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('暂无可补打的计划')));
      return;
    }
    final target = await showModalBottomSheet<Map<String, dynamic>?>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text('补打 $dateStr',
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
            ),
            const Divider(height: 1),
            ..._items.map((it) => ListTile(
                  title: Text(it['name'] ?? ''),
                  onTap: () => Navigator.pop(ctx, it),
                )),
            const Divider(height: 1),
            ListTile(
              title: const Center(child: Text('取消')),
              onTap: () => Navigator.pop(ctx),
            ),
          ],
        ),
      ),
    );
    if (target == null) return;
    try {
      await _api.makeupCheckin(target['id'] as int, dateStr);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('补卡成功'), backgroundColor: Color(0xFF6366F1)));
      }
      _load();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('补卡失败'), backgroundColor: Colors.red));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F5F7),
      appBar: AppBar(
        title: const Text('打卡成果'),
        backgroundColor: const Color(0xFF52C41A),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: EdgeInsets.zero,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
                    ),
                  ),
                  child: Row(
                    children: [
                      _heroCol('${_summary['streak_days'] ?? 0}', '连续天数'),
                      _heroDivider(),
                      _heroCol('${_summary['total_checkins'] ?? 0}', '累计打卡'),
                      _heroDivider(),
                      _heroCol('${(_summary['overall_completion_rate'] as num?)?.round() ?? 0}%', '完成率'),
                    ],
                  ),
                ),
                Container(
                  margin: const EdgeInsets.fromLTRB(16, -12, 16, 12),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
                  child: _calendarWidget(),
                ),
                Container(
                  margin: const EdgeInsets.symmetric(horizontal: 16),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
                  child: _rankWidget(),
                ),
                const SizedBox(height: 24),
              ],
            ),
    );
  }

  Widget _heroCol(String num, String label) => Expanded(
        child: Column(
          children: [
            Text(num, style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text(label, style: const TextStyle(color: Colors.white70, fontSize: 11)),
          ],
        ),
      );

  Widget _heroDivider() => Container(width: 1, height: 36, color: Colors.white24);

  Widget _calendarWidget() {
    final firstDayIdx = DateTime(_year, _month, 1).weekday % 7; // Sun=0
    final daysInMonth = DateTime(_year, _month + 1, 0).day;
    final cells = <Widget>[];
    final now = DateTime.now();
    final todayStr = '${now.year}-${_pad(now.month)}-${_pad(now.day)}';
    for (int i = 0; i < firstDayIdx; i++) {
      cells.add(const SizedBox());
    }
    for (int d = 1; d <= daysInMonth; d++) {
      final ds = '$_year-${_pad(_month)}-${_pad(d)}';
      final cnt = _calendarMap[ds] ?? 0;
      final isToday = ds == todayStr;
      final cellDate = DateTime(_year, _month, d);
      final diff = DateTime(now.year, now.month, now.day).difference(cellDate).inDays;
      final canMakeup = cnt == 0 && diff >= 1 && diff <= 3;
      cells.add(GestureDetector(
        onTap: () => _onDayTap(ds, cnt),
        child: Container(
          margin: const EdgeInsets.all(2),
          decoration: BoxDecoration(
            gradient: cnt > 0
                ? const LinearGradient(colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)])
                : null,
            color: cnt > 0
                ? null
                : (isToday ? const Color(0xFFEEF2FF) : (canMakeup ? const Color(0xFFFFF7ED) : Colors.transparent)),
            border: canMakeup ? Border.all(color: const Color(0xFFF59E0B), style: BorderStyle.solid, width: 1) : null,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Center(
            child: Text('$d',
                style: TextStyle(
                  color: cnt > 0 ? Colors.white : (isToday ? const Color(0xFF6366F1) : const Color(0xFF1F2937)),
                  fontWeight: cnt > 0 || isToday ? FontWeight.bold : FontWeight.normal,
                  fontSize: 13,
                )),
          ),
        ),
      ));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            IconButton(
              icon: const Icon(Icons.chevron_left, color: Color(0xFF6366F1)),
              onPressed: () => _changeMonth(-1),
            ),
            Text('$_year 年 $_month 月',
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
            IconButton(
              icon: const Icon(Icons.chevron_right, color: Color(0xFF6366F1)),
              onPressed: () => _changeMonth(1),
            ),
          ],
        ),
        Row(
          children: ['日', '一', '二', '三', '四', '五', '六']
              .map((w) => Expanded(
                  child: Center(
                      child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          child: Text(w, style: const TextStyle(fontSize: 11, color: Color(0xFF9CA3AF)))))))
              .toList(),
        ),
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 7,
          children: cells,
        ),
      ],
    );
  }

  Widget _rankWidget() {
    final plans = (_summary['plans'] as List?) ?? [];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('各计划完成率', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        if (plans.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Center(child: Text('暂无数据', style: TextStyle(color: Color(0xFF9CA3AF)))),
          )
        else
          ...plans.asMap().entries.map((entry) {
            final idx = entry.key;
            final p = Map<String, dynamic>.from(entry.value as Map);
            final color = _rankColors[idx % _rankColors.length];
            final rate = (p['completion_rate'] as num?)?.toDouble() ?? 0;
            return Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 20, height: 20,
                        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                        alignment: Alignment.center,
                        child: Text('${idx + 1}', style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                      ),
                      const SizedBox(width: 8),
                      Expanded(child: Text(p['name'] ?? '', style: const TextStyle(fontSize: 13))),
                      Text('${rate.round()}%', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: color)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: (rate / 100).clamp(0.0, 1.0),
                      backgroundColor: const Color(0xFFF0F0F0),
                      color: color,
                      minHeight: 6,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text('已打 ${p['done'] ?? 0} / 应打 ${p['expected'] ?? 0}',
                      style: const TextStyle(fontSize: 10, color: Color(0xFF9CA3AF))),
                ],
              ),
            );
          }).toList(),
      ],
    );
  }
}
