import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class RecommendedPlanDetailScreen extends StatefulWidget {
  const RecommendedPlanDetailScreen({super.key});

  @override
  State<RecommendedPlanDetailScreen> createState() => _RecommendedPlanDetailScreenState();
}

class _RecommendedPlanDetailScreenState extends State<RecommendedPlanDetailScreen> {
  final ApiService _apiService = ApiService();
  bool _loading = true;
  bool _joining = false;

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
      final response = await _apiService.getRecommendedPlanDetail(_planId!);
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

  Future<void> _joinPlan() async {
    setState(() => _joining = true);
    try {
      final response = await _apiService.joinRecommendedPlan(_planId!);
      if (response.statusCode == 200 && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已成功加入计划'), backgroundColor: Color(0xFF52C41A)),
        );
        Navigator.pop(context, true);
        return;
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('加入失败，请稍后重试'), backgroundColor: Colors.red),
        );
      }
    }
    if (mounted) setState(() => _joining = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('推荐计划详情'),
        backgroundColor: const Color(0xFF1890FF),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF1890FF)))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildHeader(),
                  const SizedBox(height: 20),
                  if (_plan['description'] != null) ...[
                    const Text('计划介绍', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
                    const SizedBox(height: 8),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        _plan['description'].toString(),
                        style: const TextStyle(fontSize: 14, color: Color(0xFF666666), height: 1.6),
                      ),
                    ),
                    const SizedBox(height: 20),
                  ],
                  if (_tasks.isNotEmpty) ...[
                    Text('计划任务 (${_tasks.length})', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF333333))),
                    const SizedBox(height: 12),
                    ..._tasks.asMap().entries.map((e) => _buildTaskItem(e.key + 1, e.value)),
                  ],
                  const SizedBox(height: 80),
                ],
              ),
            ),
      bottomNavigationBar: _loading
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: ElevatedButton(
                    onPressed: _joining ? null : _joinPlan,
                    style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1890FF)),
                    child: _joining
                        ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : const Text('加入此计划'),
                  ),
                ),
              ),
            ),
    );
  }

  Widget _buildHeader() {
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
          Text(
            _plan['plan_name']?.toString() ?? _plan['name']?.toString() ?? '',
            style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              if (_plan['duration_days'] != null) ...[
                Icon(Icons.calendar_today, color: Colors.white.withOpacity(0.8), size: 14),
                const SizedBox(width: 4),
                Text('${_plan['duration_days']}天', style: TextStyle(color: Colors.white.withOpacity(0.9), fontSize: 13)),
                const SizedBox(width: 16),
              ],
              if (_plan['task_count'] != null || _tasks.isNotEmpty) ...[
                Icon(Icons.checklist, color: Colors.white.withOpacity(0.8), size: 14),
                const SizedBox(width: 4),
                Text('${_plan['task_count'] ?? _tasks.length}个任务', style: TextStyle(color: Colors.white.withOpacity(0.9), fontSize: 13)),
              ],
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTaskItem(int index, Map<String, dynamic> task) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: const Color(0xFF1890FF).withOpacity(0.1),
            ),
            alignment: Alignment.center,
            child: Text('$index', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF1890FF))),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(task['name']?.toString() ?? task['task_name']?.toString() ?? '', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
                if (task['description'] != null)
                  Text(task['description'].toString(), style: TextStyle(fontSize: 12, color: Colors.grey[400])),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
