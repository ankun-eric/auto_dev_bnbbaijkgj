import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/checkin_points_progress.dart';

class CheckinListScreen extends StatefulWidget {
  const CheckinListScreen({super.key});

  @override
  State<CheckinListScreen> createState() => _CheckinListScreenState();
}

class _CheckinListScreenState extends State<CheckinListScreen> {
  final ApiService _apiService = ApiService();
  final _progressKey = GlobalKey<CheckinPointsProgressState>();
  bool _loading = true;
  List<Map<String, dynamic>> _items = [];

  @override
  void initState() {
    super.initState();
    _loadItems();
  }

  Future<void> _loadItems() async {
    try {
      final response = await _apiService.getCheckinItems();
      if (response.statusCode == 200 && mounted) {
        final data = response.data;
        List items = [];
        if (data is Map && data['items'] is List) {
          items = data['items'] as List;
        } else if (data is List) {
          items = data;
        }
        setState(() {
          _items = items.map((e) {
            final m = Map<String, dynamic>.from(e as Map);
            m['is_checked'] = m['today_completed'] ?? m['is_checked'] ?? false;
            return m;
          }).toList();
          _loading = false;
        });
        return;
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _deleteItem(int id) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('确认删除'),
        content: const Text('确定要删除这个打卡项目吗？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('删除', style: TextStyle(color: Colors.red))),
        ],
      ),
    );
    if (confirmed == true) {
      try {
        await _apiService.deleteCheckinItem(id);
        _loadItems();
      } catch (_) {}
    }
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

  Future<void> _checkin(Map<String, dynamic> item) async {
    if (item['target_value'] != null) {
      final controller = TextEditingController();
      final result = await showDialog<double>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('${item['name']} 打卡'),
          content: TextField(
            controller: controller,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              hintText: '请输入实际值',
              suffixText: item['target_unit']?.toString() ?? '',
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
            TextButton(
              onPressed: () {
                final val = double.tryParse(controller.text);
                Navigator.pop(ctx, val);
              },
              child: const Text('确认打卡'),
            ),
          ],
        ),
      );
      if (result != null) {
        try {
          final response = await _apiService.checkinCheckinItem(item['id'] as int, actualValue: result, isCompleted: true);
          _showPointsSnackBar(response.data is Map ? response.data as Map<String, dynamic> : null);
          _loadItems();
        } catch (_) {}
      }
    } else {
      try {
        final response = await _apiService.checkinCheckinItem(item['id'] as int, isCompleted: true);
        _showPointsSnackBar(response.data is Map ? response.data as Map<String, dynamic> : null);
        _loadItems();
      } catch (_) {}
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('健康打卡'),
        backgroundColor: const Color(0xFF52C41A),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
          : _items.isEmpty
              ? _buildEmpty()
              : RefreshIndicator(
                  color: const Color(0xFF52C41A),
                  onRefresh: () async {
                    await _loadItems();
                    _progressKey.currentState?.loadProgress();
                  },
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _items.length + 1,
                    itemBuilder: (context, index) {
                      if (index == 0) {
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: CheckinPointsProgress(key: _progressKey),
                        );
                      }
                      return _buildCard(_items[index - 1]);
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          final result = await Navigator.pushNamed(context, '/hp-checkin-form');
          if (result == true) _loadItems();
        },
        backgroundColor: const Color(0xFF52C41A),
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.check_circle_outline, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 16),
          Text('暂无打卡项目', style: TextStyle(fontSize: 16, color: Colors.grey[400])),
          const SizedBox(height: 8),
          Text('点击右下角按钮添加', style: TextStyle(fontSize: 13, color: Colors.grey[300])),
        ],
      ),
    );
  }

  Widget _buildCard(Map<String, dynamic> item) {
    final isChecked = item['is_checked'] == true;
    final streakDays = item['streak_days'] ?? 0;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8, offset: const Offset(0, 2)),
        ],
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: isChecked ? null : () => _checkin(item),
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isChecked ? const Color(0xFF52C41A) : const Color(0xFF52C41A).withOpacity(0.1),
                border: isChecked ? null : Border.all(color: const Color(0xFF52C41A).withOpacity(0.3), width: 2),
              ),
              child: Icon(
                isChecked ? Icons.check : Icons.touch_app_outlined,
                color: isChecked ? Colors.white : const Color(0xFF52C41A),
                size: 20,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item['name']?.toString() ?? '',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w500,
                    color: isChecked ? Colors.grey[400] : const Color(0xFF333333),
                    decoration: isChecked ? TextDecoration.lineThrough : null,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    if (item['target_value'] != null)
                      Text(
                        '目标: ${item['target_value']} ${item['target_unit'] ?? ''}',
                        style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                      ),
                    if (item['target_value'] != null) const SizedBox(width: 12),
                    if (streakDays > 0)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: const Color(0xFF52C41A).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text('连续 $streakDays 天', style: const TextStyle(fontSize: 11, color: Color(0xFF52C41A))),
                      ),
                  ],
                ),
              ],
            ),
          ),
          PopupMenuButton<String>(
            icon: Icon(Icons.more_vert, color: Colors.grey[400]),
            onSelected: (val) {
              if (val == 'edit') {
                Navigator.pushNamed(context, '/hp-checkin-form', arguments: item).then((r) {
                  if (r == true) _loadItems();
                });
              } else if (val == 'delete') {
                _deleteItem(item['id'] as int);
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(value: 'edit', child: Text('编辑')),
              const PopupMenuItem(value: 'delete', child: Text('删除', style: TextStyle(color: Colors.red))),
            ],
          ),
        ],
      ),
    );
  }
}
