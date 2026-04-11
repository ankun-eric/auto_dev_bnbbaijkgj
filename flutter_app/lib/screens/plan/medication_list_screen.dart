import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/checkin_points_progress.dart';

class MedicationListScreen extends StatefulWidget {
  const MedicationListScreen({super.key});

  @override
  State<MedicationListScreen> createState() => _MedicationListScreenState();
}

class _MedicationListScreenState extends State<MedicationListScreen> {
  final ApiService _apiService = ApiService();
  final _progressKey = GlobalKey<CheckinPointsProgressState>();
  bool _loading = true;
  List<Map<String, dynamic>> _medications = [];

  static const _timePeriodOrder = ['morning', 'noon', 'afternoon', 'evening', 'night'];
  static const _timePeriodLabels = {
    'morning': '早上',
    'noon': '中午',
    'afternoon': '下午',
    'evening': '晚上',
    'night': '睡前',
  };
  static const _timePeriodIcons = {
    'morning': Icons.wb_sunny_outlined,
    'noon': Icons.light_mode_outlined,
    'afternoon': Icons.wb_cloudy_outlined,
    'evening': Icons.nights_stay_outlined,
    'night': Icons.bedtime_outlined,
  };

  @override
  void initState() {
    super.initState();
    _loadMedications();
  }

  Future<void> _loadMedications() async {
    try {
      final response = await _apiService.getMedications();
      if (response.statusCode == 200 && mounted) {
        final data = response.data;
        List items = [];
        if (data is Map && data['groups'] is Map) {
          final groups = data['groups'] as Map;
          for (final groupItems in groups.values) {
            if (groupItems is List) {
              items.addAll(groupItems);
            }
          }
        } else if (data is Map && data['items'] is List) {
          items = data['items'] as List;
        } else if (data is List) {
          items = data;
        }
        setState(() {
          _medications = items.map((e) {
            final m = Map<String, dynamic>.from(e as Map);
            m['is_checked'] = m['today_checked'] ?? m['is_checked'] ?? false;
            return m;
          }).toList();
          _loading = false;
        });
        return;
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Map<String, List<Map<String, dynamic>>> _groupByTimePeriod() {
    final groups = <String, List<Map<String, dynamic>>>{};
    for (final m in _medications) {
      final period = m['time_period']?.toString() ?? 'morning';
      groups.putIfAbsent(period, () => []).add(m);
    }
    final sorted = <String, List<Map<String, dynamic>>>{};
    for (final key in _timePeriodOrder) {
      if (groups.containsKey(key)) sorted[key] = groups[key]!;
    }
    for (final key in groups.keys) {
      if (!sorted.containsKey(key)) sorted[key] = groups[key]!;
    }
    return sorted;
  }

  Future<void> _deleteMedication(int id) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('确认删除'),
        content: const Text('确定要删除这条用药提醒吗？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('删除', style: TextStyle(color: Colors.red))),
        ],
      ),
    );
    if (confirmed == true) {
      try {
        await _apiService.deleteMedication(id);
        _loadMedications();
      } catch (_) {}
    }
  }

  Future<void> _togglePause(Map<String, dynamic> med) async {
    try {
      final id = med['id'] as int;
      final isPaused = med['is_paused'] == true;
      await _apiService.pauseMedication(id, !isPaused);
      _loadMedications();
    } catch (_) {}
  }

  void _showPointsSnackBar(Map<String, dynamic>? responseData) {
    if (!mounted || responseData == null) return;
    final pointsEarned = responseData['points_earned'] as int? ?? 0;
    final limitReached = responseData['points_limit_reached'] == true;
    if (pointsEarned > 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('打卡成功，获得 $pointsEarned 积分！'), backgroundColor: const Color(0xFF52C41A)),
      );
    } else if (limitReached) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('打卡成功！今日打卡积分已达上限'), backgroundColor: Color(0xFFFA8C16)),
      );
    }
    _progressKey.currentState?.loadProgress();
  }

  Future<void> _checkin(Map<String, dynamic> med) async {
    try {
      final response = await _apiService.checkinMedication(med['id'] as int);
      _showPointsSnackBar(response.data is Map ? response.data as Map<String, dynamic> : null);
      _loadMedications();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('用药提醒'),
        backgroundColor: const Color(0xFFFA8C16),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFFFA8C16)))
          : _medications.isEmpty
              ? _buildEmpty()
              : RefreshIndicator(
                  color: const Color(0xFFFA8C16),
                  onRefresh: () async {
                    await _loadMedications();
                    _progressKey.currentState?.loadProgress();
                  },
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: CheckinPointsProgress(key: _progressKey),
                      ),
                      ..._buildGroupedList(),
                    ],
                  ),
                ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          final result = await Navigator.pushNamed(context, '/hp-medication-form');
          if (result == true) _loadMedications();
        },
        backgroundColor: const Color(0xFFFA8C16),
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.medication_outlined, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 16),
          Text('暂无用药提醒', style: TextStyle(fontSize: 16, color: Colors.grey[400])),
          const SizedBox(height: 8),
          Text('点击右下角按钮添加', style: TextStyle(fontSize: 13, color: Colors.grey[300])),
        ],
      ),
    );
  }

  List<Widget> _buildGroupedList() {
    final groups = _groupByTimePeriod();
    final widgets = <Widget>[];
    for (final entry in groups.entries) {
      final period = entry.key;
      final meds = entry.value;
      widgets.add(
        Padding(
          padding: const EdgeInsets.only(top: 8, bottom: 8),
          child: Row(
            children: [
              Icon(_timePeriodIcons[period] ?? Icons.access_time, size: 18, color: const Color(0xFFFA8C16)),
              const SizedBox(width: 6),
              Text(
                _timePeriodLabels[period] ?? period,
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFFFA8C16)),
              ),
            ],
          ),
        ),
      );
      for (final med in meds) {
        widgets.add(_buildMedicationCard(med));
      }
    }
    return widgets;
  }

  Widget _buildMedicationCard(Map<String, dynamic> med) {
    final isPaused = med['is_paused'] == true;
    final isChecked = med['is_checked'] == true;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isPaused ? Colors.grey[50] : Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8, offset: const Offset(0, 2)),
        ],
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: isChecked || isPaused ? null : () => _checkin(med),
            child: Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isChecked ? const Color(0xFFFA8C16) : Colors.transparent,
                border: Border.all(
                  color: isChecked ? const Color(0xFFFA8C16) : (isPaused ? Colors.grey[300]! : Colors.grey[300]!),
                  width: 2,
                ),
              ),
              child: isChecked ? const Icon(Icons.check, size: 16, color: Colors.white) : null,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  med['medicine_name']?.toString() ?? '',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                    color: isPaused ? Colors.grey[400] : const Color(0xFF333333),
                    decoration: isPaused ? TextDecoration.lineThrough : null,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  [
                    if (med['dosage'] != null) med['dosage'].toString(),
                    if (med['remind_time'] != null) med['remind_time'].toString(),
                  ].join(' · '),
                  style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                ),
                if (med['notes'] != null && (med['notes'] as String).isNotEmpty)
                  Text(med['notes'] as String, style: TextStyle(fontSize: 11, color: Colors.grey[400])),
              ],
            ),
          ),
          PopupMenuButton<String>(
            icon: Icon(Icons.more_vert, color: Colors.grey[400]),
            onSelected: (val) {
              switch (val) {
                case 'edit':
                  Navigator.pushNamed(context, '/hp-medication-form', arguments: med).then((r) {
                    if (r == true) _loadMedications();
                  });
                  break;
                case 'pause':
                  _togglePause(med);
                  break;
                case 'delete':
                  _deleteMedication(med['id'] as int);
                  break;
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(value: 'edit', child: Text('编辑')),
              PopupMenuItem(value: 'pause', child: Text(isPaused ? '恢复' : '暂停')),
              const PopupMenuItem(value: 'delete', child: Text('删除', style: TextStyle(color: Colors.red))),
            ],
          ),
        ],
      ),
    );
  }
}
