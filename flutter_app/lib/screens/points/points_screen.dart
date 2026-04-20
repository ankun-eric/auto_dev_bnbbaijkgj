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
  int _availablePoints = 0;
  int _todayEarned = 0;
  bool _signedToday = false;
  List<Map<String, dynamic>> _tasks = [];
  bool _tasksError = false;
  bool _tasksLoaded = false;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    if (mounted && !_loading) setState(() => _loading = true);

    int totalPoints = _totalPoints;
    int availablePoints = _availablePoints;
    int todayEarned = _todayEarned;
    bool signedToday = _signedToday;
    try {
      final summaryRes = await _apiService.getPointsSummary();
      final summary = summaryRes.data is Map ? summaryRes.data as Map<String, dynamic> : <String, dynamic>{};
      totalPoints = (summary['total_points'] is int)
          ? summary['total_points'] as int
          : int.tryParse('${summary['total_points'] ?? 0}') ?? 0;
      // Bug #4: 可用积分统一读取后端 available_points / available 字段
      final avail = summary['available_points'] ?? summary['available'] ?? totalPoints;
      availablePoints = (avail is int) ? avail : int.tryParse('$avail') ?? totalPoints;
      todayEarned = (summary['today_earned_points'] is int)
          ? summary['today_earned_points'] as int
          : int.tryParse('${summary['today_earned_points'] ?? 0}') ?? 0;
      signedToday = summary['signed_today'] == true;
    } catch (_) {}

    List<Map<String, dynamic>> tasks = [];
    bool tasksError = false;
    try {
      final tasksRes = await _apiService.getPointsTasks();
      final tasksData = tasksRes.data is Map ? tasksRes.data as Map<String, dynamic> : <String, dynamic>{};
      final items = tasksData['items'];
      tasks = (items is List)
          ? items.map((e) => Map<String, dynamic>.from(e as Map)).toList()
          : <Map<String, dynamic>>[];
    } catch (_) {
      tasksError = true;
    }

    if (!mounted) return;
    setState(() {
      _totalPoints = totalPoints;
      _availablePoints = availablePoints;
      _todayEarned = todayEarned;
      _signedToday = signedToday;
      _tasks = tasks;
      _tasksError = tasksError;
      _tasksLoaded = true;
      _loading = false;
    });
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
    // Bug 7：后端已统一为 /health-profile；/profile/edit 兼容旧值
    // Bug 8：first_order 已被后端过滤，前端不再硬编码 /services 等映射
    const routeMap = {
      '/health-profile': '/health-profile',
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
                        color: Color(0xFFC8E6C9),
                      ),
                      child: Column(
                        children: [
                          const Text('我的可用积分', style: TextStyle(color: Color(0xFF1B5E20), fontSize: 14)),
                          const SizedBox(height: 8),
                          Text('$_availablePoints', style: const TextStyle(color: Color(0xFF1B5E20), fontSize: 44, fontWeight: FontWeight.bold)),
                          const SizedBox(height: 8),
                          Text(
                            _todayEarned > 0 ? '今天获得积分 +$_todayEarned' : '今天还未获得积分，快去赚取吧',
                            style: const TextStyle(color: Color(0xFF2E7D32), fontSize: 13),
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
                    if (_tasksError)
                      _buildTasksErrorView()
                    else if (_tasksLoaded && _tasks.isEmpty)
                      _buildTasksEmptyView()
                    else
                      ..._tasks.map(_buildTaskCard).toList(),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildTasksErrorView() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 40),
      child: Column(
        children: [
          const Text('⚠️', style: TextStyle(fontSize: 40)),
          const SizedBox(height: 12),
          Text('加载失败', style: TextStyle(fontSize: 14, color: Colors.grey[600])),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: _loadData,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF52C41A),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 8),
            ),
            child: const Text('点击重试'),
          ),
        ],
      ),
    );
  }

  Widget _buildTasksEmptyView() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 40),
      child: Column(
        children: [
          const Text('📋', style: TextStyle(fontSize: 40)),
          const SizedBox(height: 12),
          Text('暂无任务', style: TextStyle(fontSize: 14, color: Colors.grey[600])),
        ],
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
    final baseCategoryColor = category == 'daily' ? const Color(0xFF52C41A) : category == 'once' ? const Color(0xFFFA8C16) : const Color(0xFF1890FF);
    final onceDone = completed && category == 'once';
    final disabled = onceDone || (actionType == 'sign_in' && _signedToday);
    final btnText = onceDone ? '✓ 已完成'
        : (actionType == 'sign_in' && _signedToday) ? '已签到'
        : (completed && category == 'daily') ? '已完成'
        : (actionType == 'sign_in') ? '去签到'
        : (task['key'] == 'complete_profile') ? '去完善'
        : '去完成';

    final categoryColor = onceDone ? const Color(0xFFBFBFBF) : baseCategoryColor;
    final titleColor = onceDone ? const Color(0xFF999999) : const Color(0xFF333333);
    final pointsColor = onceDone ? const Color(0xFFBFBFBF) : const Color(0xFFFA8C16);
    final subtitleColor = onceDone ? const Color(0xFFBFBFBF) : Colors.grey[600];

    return Opacity(
      opacity: onceDone ? 0.7 : 1.0,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: onceDone ? const Color(0xFFF5F5F5) : Colors.white,
          borderRadius: BorderRadius.circular(12),
        ),
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
                      Text(
                        title,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: titleColor,
                          decoration: onceDone ? TextDecoration.lineThrough : TextDecoration.none,
                        ),
                      ),
                      if (onceDone)
                        const Text('✓ 已完成', style: TextStyle(fontSize: 11, color: Color(0xFF52C41A))),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                        decoration: BoxDecoration(
                          border: Border.all(color: categoryColor, width: 1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(categoryLabel, style: TextStyle(fontSize: 10, color: categoryColor)),
                      ),
                      Text('+$points 积分', style: TextStyle(fontSize: 12, color: pointsColor)),
                    ],
                  ),
                  if (subtitle != null && subtitle.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(subtitle, style: TextStyle(fontSize: 12, color: subtitleColor)),
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
      ),
    );
  }
}
