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
  bool _loading = true;
  bool _signing = false;
  int _totalPoints = 0;
  int _todayEarned = 0;
  bool _signedToday = false;
  List<Map<String, dynamic>> _tasks = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      final results = await Future.wait([
        _apiService.getPointsSummary(),
        _apiService.getPointsTasks(),
      ]);
      if (!mounted) return;
      final summary = results[0].data is Map ? results[0].data as Map<String, dynamic> : <String, dynamic>{};
      final tasksData = results[1].data is Map ? results[1].data as Map<String, dynamic> : <String, dynamic>{};
      final items = tasksData['items'];
      setState(() {
        _totalPoints = summary['total_points'] ?? 0;
        _todayEarned = summary['today_earned_points'] ?? 0;
        _signedToday = summary['signed_today'] == true;
        _tasks = (items is List)
            ? items.map((e) => Map<String, dynamic>.from(e as Map)).toList()
            : [];
        _loading = false;
      });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _doSignIn() async {
    if (_signedToday || _signing) return;
    setState(() => _signing = true);
    try {
      final res = await _apiService.pointsCheckin();
      final data = res.data is Map ? res.data as Map : {};
      final earned = data['points_earned'] ?? 0;
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(earned > 0 ? '签到成功 +$earned' : '签到成功'), backgroundColor: const Color(0xFF52C41A)),
        );
      }
      _loadData();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('签到失败或今日已签到'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _signing = false);
    }
  }

  void _handleTask(Map<String, dynamic> task) {
    final actionType = task['action_type']?.toString();
    if (actionType == 'sign_in') {
      _doSignIn();
      return;
    }
    final completed = task['completed'] == true;
    final category = task['category']?.toString();
    if (completed && category == 'once') return;
    final route = task['route']?.toString();
    if (route == null || route.isEmpty) return;

    // 路由映射
    const routeMap = {
      '/profile/edit': '/health-profile',
      '/health-plan': '/health-plan',
      '/orders?tab=pending_review': '/orders',
      '/invite': '/invite',
      '/products': '/products',
      '/mall': '/products',
    };
    final target = routeMap[route] ?? route;
    Navigator.pushNamed(context, target);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F5F5),
      appBar: CustomAppBar(
        title: '积分中心',
        actions: [
          TextButton(
            onPressed: () => Navigator.pushNamed(context, '/points-records'),
            child: const Text('积分详情 ›', style: TextStyle(color: Colors.white)),
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
                      padding: const EdgeInsets.fromLTRB(24, 24, 24, 36),
                      decoration: const BoxDecoration(
                        gradient: LinearGradient(colors: [Color(0xFF52C41A), Color(0xFF13C2C2)]),
                      ),
                      child: Column(
                        children: [
                          const Text('我的总积分', style: TextStyle(color: Colors.white70, fontSize: 14)),
                          const SizedBox(height: 8),
                          Text('$_totalPoints', style: const TextStyle(color: Colors.white, fontSize: 44, fontWeight: FontWeight.bold)),
                          const SizedBox(height: 8),
                          Text(
                            _todayEarned > 0 ? '今天获得积分 +$_todayEarned' : '今天还未获得积分，快去赚取吧',
                            style: const TextStyle(color: Colors.white, fontSize: 13),
                          ),
                        ],
                      ),
                    ),
                    Transform.translate(
                      offset: const Offset(0, -16),
                      child: Container(
                        margin: const EdgeInsets.symmetric(horizontal: 16),
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
                        child: InkWell(
                          onTap: () => Navigator.pushNamed(context, '/points-mall'),
                          child: const Row(
                            children: [
                              Text('🎁', style: TextStyle(fontSize: 28)),
                              SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text('积分商城', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                                    Text('用积分兑换好礼', style: TextStyle(fontSize: 12, color: Colors.grey)),
                                  ],
                                ),
                              ),
                              Icon(Icons.chevron_right, color: Colors.grey),
                            ],
                          ),
                        ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: const [
                          Text('日常任务', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                          Text('完成任务赚积分', style: TextStyle(fontSize: 12, color: Colors.grey)),
                        ],
                      ),
                    ),
                    ..._tasks.map(_buildTaskCard).toList(),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildTaskCard(Map<String, dynamic> task) {
    final title = task['title']?.toString() ?? '';
    final subtitle = task['subtitle']?.toString();
    final points = task['points'] ?? 0;
    final completed = task['completed'] == true;
    final category = task['category']?.toString();
    final actionType = task['action_type']?.toString();
    final categoryLabel = category == 'daily' ? '每日' : category == 'once' ? '一次性' : '可重复';
    final categoryColor = category == 'daily' ? const Color(0xFF52C41A) : category == 'once' ? const Color(0xFFFA8C16) : const Color(0xFF1890FF);
    final disabled = (completed && category == 'once') || (actionType == 'sign_in' && _signedToday);
    final btnText = (completed && category == 'once') ? '✅ 已完成'
        : (actionType == 'sign_in' && _signedToday) ? '已签到'
        : (completed && category == 'daily') ? '已完成'
        : (actionType == 'sign_in') ? '去签到'
        : (task['key'] == 'complete_profile') ? '去完善'
        : '去完成';

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(
                        border: Border.all(color: categoryColor, width: 1),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(categoryLabel, style: TextStyle(fontSize: 10, color: categoryColor)),
                    ),
                    Text('+$points 积分', style: const TextStyle(fontSize: 12, color: Color(0xFFFA8C16))),
                  ],
                ),
                if (subtitle != null && subtitle.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(subtitle, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          ElevatedButton(
            onPressed: disabled ? null : () => _handleTask(task),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF52C41A),
              disabledBackgroundColor: const Color(0xFFE8E8E8),
              disabledForegroundColor: Colors.grey[600],
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              minimumSize: const Size(72, 32),
            ),
            child: Text(btnText, style: const TextStyle(fontSize: 12, color: Colors.white)),
          ),
        ],
      ),
    );
  }
}
