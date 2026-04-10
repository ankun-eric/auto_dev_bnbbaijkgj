import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class UserPlanDetailScreen extends StatefulWidget {
  const UserPlanDetailScreen({super.key});

  @override
  State<UserPlanDetailScreen> createState() => _UserPlanDetailScreenState();
}

class _UserPlanDetailScreenState extends State<UserPlanDetailScreen> {
  final ApiService _apiService = ApiService();
  bool _loading = true;

  Map<String, dynamic> _plan = {};
  List<Map<String, dynamic>> _tasks = [];
  int? _planId;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_planId == null) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is Map<String, dynamic>) {
        _planId = args['id'] as int?;
        _plan = args;
        if (_planId != null) _loadDetail();
      }
    }
  }

  Future<void> _loadDetail() async {
    try {
      final response = await _apiService.getUserPlanDetail(_planId!);
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map ? response.data as Map<String, dynamic> : <String, dynamic>{};
        setState(() {
          _plan = data;
          final taskList = data['tasks'];
          if (taskList is List) {
            _tasks = taskList.map((e) => Map<String, dynamic>.from(e as Map)).toList();
          }
          _loading = false;
        });
        return;
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _checkinTask(Map<String, dynamic> task) async {
    try {
      final taskId = task['id'] as int;
      await _apiService.checkinUserPlanTask(_planId!, taskId);
      _loadDetail();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final progress = (_plan['progress'] ?? 0).toDouble();
    final planName = _plan['plan_name']?.toString() ?? _plan['name']?.toString() ?? '计划详情';

    return Scaffold(
      appBar: AppBar(
        title: Text(planName, maxLines: 1, overflow: TextOverflow.ellipsis),
        backgroundColor: const Color(0xFF1890FF),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF1890FF)))
          : RefreshIndicator(
              color: const Color(0xFF1890FF),
              onRefresh: _loadDetail,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildProgressCard(progress),
                    const SizedBox(height: 20),
                    if (_plan['description'] != null && (_plan['description'] as String).isNotEmpty) ...[
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: const Color(0xFF1890FF).withOpacity(0.06),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          _plan['description'].toString(),
                          style: const TextStyle(fontSize: 14, color: Color(0xFF666666), height: 1.5),
                        ),
                      ),
                      const SizedBox(height: 20),
                    ],
                    Text('今日任务 (${_tasks.length})', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
                    const SizedBox(height: 12),
                    if (_tasks.isEmpty)
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.symmetric(vertical: 32),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          children: [
                            Icon(Icons.check_circle, size: 48, color: Colors.grey[300]),
                            const SizedBox(height: 12),
                            Text('暂无任务', style: TextStyle(fontSize: 14, color: Colors.grey[400])),
                          ],
                        ),
                      )
                    else
                      ..._tasks.map(_buildTaskCard),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildProgressCard(double progress) {
    final completedCount = _tasks.where((t) => t['is_completed'] == true || t['is_checked'] == true).length;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        gradient: const LinearGradient(colors: [Color(0xFF1890FF), Color(0xFF13C2C2)]),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '进度 ${progress.toInt()}%',
                style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
              ),
              Text(
                '$completedCount/${_tasks.length} 完成',
                style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 14),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress / 100,
              backgroundColor: Colors.white.withOpacity(0.2),
              valueColor: const AlwaysStoppedAnimation(Colors.white),
              minHeight: 8,
            ),
          ),
          if (_plan['duration_days'] != null) ...[
            const SizedBox(height: 8),
            Text(
              '计划周期: ${_plan['duration_days']} 天',
              style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 13),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTaskCard(Map<String, dynamic> task) {
    final done = task['today_completed'] == true || task['is_completed'] == true || task['is_checked'] == true;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: done ? Border.all(color: const Color(0xFF52C41A).withOpacity(0.3)) : null,
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.03), blurRadius: 6, offset: const Offset(0, 2))],
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: done ? null : () => _checkinTask(task),
            child: Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: done ? const Color(0xFF52C41A) : Colors.transparent,
                border: Border.all(color: done ? const Color(0xFF52C41A) : Colors.grey[300]!, width: 2),
              ),
              child: done ? const Icon(Icons.check, size: 16, color: Colors.white) : null,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  task['name']?.toString() ?? task['task_name']?.toString() ?? '',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                    decoration: done ? TextDecoration.lineThrough : null,
                    color: done ? Colors.grey[400] : const Color(0xFF333333),
                  ),
                ),
                if (task['description'] != null)
                  Text(task['description'].toString(), style: TextStyle(fontSize: 12, color: Colors.grey[400])),
              ],
            ),
          ),
          if (!done)
            GestureDetector(
              onTap: () => _checkinTask(task),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFF1890FF).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Text('打卡', style: TextStyle(fontSize: 13, color: Color(0xFF1890FF), fontWeight: FontWeight.w500)),
              ),
            ),
        ],
      ),
    );
  }
}
