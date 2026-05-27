// [PRD-AIHOME-CARE-V1 2026-05-27] Flutter 关怀模式首页
import 'dart:async';
import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class CareHomeScreen extends StatefulWidget {
  const CareHomeScreen({super.key});

  @override
  State<CareHomeScreen> createState() => _CareHomeScreenState();
}

class _CareHomeScreenState extends State<CareHomeScreen> {
  Map<String, dynamic>? welcome;
  Map<String, dynamic>? cards;
  int sosStage = 0; // 0=normal,1=countdown,2=picker,3=calling,4=delivered
  int sosCountdown = 5;
  int? sosEventId;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final w = await ApiService().dio.get('/api/care-v1/home/welcome');
      final c = await ApiService().dio.get('/api/care-v1/home/proactive-cards');
      setState(() {
        welcome = (w.data?['data']) as Map<String, dynamic>?;
        cards = (c.data?['data']) as Map<String, dynamic>?;
      });
    } catch (_) {}
  }

  void _startSos(String source) async {
    setState(() {
      sosStage = 1;
      sosCountdown = 5;
    });
    try {
      final r = await ApiService().dio.post('/api/care-v1/sos/events', data: {
        'trigger_source': source,
      });
      sosEventId = r.data?['data']?['id'] as int?;
    } catch (_) {}
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      setState(() {
        sosCountdown -= 1;
        if (sosCountdown <= 0) {
          t.cancel();
          sosStage = 2;
        }
      });
    });
  }

  Future<void> _resolve(String status) async {
    if (sosEventId != null) {
      try {
        await ApiService().dio.put(
          '/api/care-v1/sos/events/$sosEventId/resolve',
          data: {'status': status},
        );
      } catch (_) {}
    }
  }

  void _cancelSos() {
    _timer?.cancel();
    _resolve('cancelled');
    setState(() {
      sosStage = 0;
      sosEventId = null;
    });
  }

  void _dispatch120() {
    _resolve('dispatched_120');
    setState(() => sosStage = 3);
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => sosStage = 4);
    });
  }

  void _dispatchFamily() {
    _resolve('dispatched_family');
    setState(() => sosStage = 3);
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => sosStage = 4);
    });
  }

  void _closeSos() {
    _resolve('closed');
    setState(() {
      sosStage = 0;
      sosEventId = null;
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (sosStage == 1) return _buildStage1();
    if (sosStage == 2) return _buildStage2();
    if (sosStage == 3) return _buildStage3();
    if (sosStage == 4) return _buildStage4();
    return _buildMain();
  }

  Widget _buildStage1() {
    return Scaffold(
      backgroundColor: const Color(0xFFE53935),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('正在为您呼叫救援...',
                style: TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.w700)),
            const SizedBox(height: 24),
            Text('$sosCountdown',
                style: const TextStyle(color: Colors.white, fontSize: 120, fontWeight: FontWeight.w900)),
            const SizedBox(height: 32),
            SizedBox(
              width: 280,
              height: 60,
              child: ElevatedButton(
                onPressed: _cancelSos,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: const Color(0xFFE53935),
                  textStyle: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
                ),
                child: const Text('我没事 · 取消'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStage2() {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Text('请选择呼叫对象', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
                const SizedBox(height: 32),
                _bigButton('🔴 呼叫 120 · 急救中心', const Color(0xFFE53935), _dispatch120, height: 110),
                const SizedBox(height: 16),
                _bigButton('👨‍👩‍👧 呼叫家人', const Color(0xFF43A047), _dispatchFamily, height: 110),
                const SizedBox(height: 24),
                TextButton(onPressed: _cancelSos, child: const Text('先取消，我再看看', style: TextStyle(color: Colors.grey))),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStage3() {
    return const Scaffold(
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('正在呼叫 120...', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
              SizedBox(height: 24),
              CircularProgressIndicator(color: Color(0xFFE53935)),
              SizedBox(height: 32),
              Text('✅ 已发送位置短信\n✅ 已附健康摘要\n✅ 已通知家人',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 16, height: 1.9, color: Colors.grey)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStage4() {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F6FB),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            children: [
              const SizedBox(height: 40),
              const Icon(Icons.check_circle, color: Color(0xFF43A047), size: 80),
              const SizedBox(height: 8),
              const Text('求救已送达',
                  style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: Color(0xFF43A047))),
              const SizedBox(height: 24),
              _cardBox(const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('📞 120 接听 ✓', style: TextStyle(fontSize: 16, height: 1.9)),
                  Text('🚑 救护车出发 ✓', style: TextStyle(fontSize: 16, height: 1.9)),
                  Text('⏱ 预计 8 分钟到达', style: TextStyle(fontSize: 16, height: 1.9)),
                ],
              )),
              const SizedBox(height: 16),
              _cardBox(const Text('👨‍👩‍👧 李子（女儿）已查看 · 正在赶来', style: TextStyle(fontSize: 16))),
              const Spacer(),
              SizedBox(
                width: double.infinity,
                child: _bigButton('我已安全', const Color(0xFF43A047), _closeSos, height: 60),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _cardBox(Widget child) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
      child: child,
    );
  }

  Widget _bigButton(String text, Color color, VoidCallback onTap, {double height = 56}) {
    return SizedBox(
      width: double.infinity,
      height: height,
      child: ElevatedButton(
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: color,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          textStyle: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
        ),
        child: Text(text),
      ),
    );
  }

  Widget _buildMain() {
    final hb = cards?['health_brief'] as Map<String, dynamic>?;
    final mr = cards?['med_reminder'] as Map<String, dynamic>?;
    final hs = cards?['home_safety'] as Map<String, dynamic>?;

    return Scaffold(
      backgroundColor: const Color(0xFFFFF5E8),
      body: Stack(
        children: [
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.only(bottom: 120),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // 顶栏
                  Container(
                    color: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Icon(Icons.menu, color: Colors.grey),
                        const Row(children: [
                          CircleAvatar(backgroundColor: Color(0xFF1976D2), radius: 18, child: Text('康', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800))),
                          SizedBox(width: 8),
                          Text('宾尼小康', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                        ]),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(colors: [Color(0xFFFF9156), Color(0xFFFF6B3D)]),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: const Text('👵 关怀模式 ▼',
                              style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w700)),
                        ),
                      ],
                    ),
                  ),
                  // 欢迎区
                  Padding(
                    padding: const EdgeInsets.fromLTRB(22, 22, 22, 14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          welcome != null ? '${welcome!['nickname']}，${welcome!['greeting']}' : '您好，欢迎使用 ☀️',
                          style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: Color(0xFF3D2E1F)),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          (welcome?['care_text'] as String?) ?? '今天也要好好照顾自己 ❤',
                          style: const TextStyle(fontSize: 18, color: Color(0xFF5A4838)),
                        ),
                      ],
                    ),
                  ),
                  // 健康简报
                  if (hb != null)
                    _briefCard(hb),
                  if (mr != null) _medCard(mr),
                  if (hs != null) _safetyCard(hs),
                ],
              ),
            ),
          ),
          // SOS 悬浮球
          Positioned(
            right: 16,
            bottom: 96,
            child: GestureDetector(
              onTap: () => _startSos('floating_button'),
              child: Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: const Color(0xFFE53935),
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(color: const Color(0xFFE53935).withOpacity(0.4), blurRadius: 24, spreadRadius: 4),
                  ],
                ),
                alignment: Alignment.center,
                child: const Text('SOS', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16)),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _briefCard(Map<String, dynamic> hb) {
    final bp = hb['blood_pressure'] as Map<String, dynamic>;
    final bg = hb['blood_glucose'] as Map<String, dynamic>;
    final sleep = hb['sleep'] as Map<String, dynamic>;
    final steps = hb['steps'] as Map<String, dynamic>;
    return Container(
      margin: const EdgeInsets.fromLTRB(22, 0, 22, 16),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('🟢 健康简报 · 今日', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF43A047))),
          const SizedBox(height: 12),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 8,
            crossAxisSpacing: 12,
            childAspectRatio: 2.2,
            children: [
              _metric('🩸 血压', '${bp['systolic']}/${bp['diastolic']}', 'mmHg', bp['abnormal'] == true),
              _metric('🩸 血糖', '${bg['value']}', '${bg['unit']}', bg['abnormal'] == true),
              _metric('😴 睡眠', '${sleep['hours']}h', '', false),
              _metric('👣 步数', '${steps['value']}', '', false),
            ],
          ),
        ],
      ),
    );
  }

  Widget _metric(String label, String val, String unit, bool abnormal) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 14, color: Colors.grey)),
        Text(val, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: abnormal ? const Color(0xFFE53935) : const Color(0xFF3D2E1F))),
        if (unit.isNotEmpty) Text(unit, style: const TextStyle(fontSize: 12, color: Colors.grey)),
      ],
    );
  }

  Widget _medCard(Map<String, dynamic> mr) {
    final items = (mr['items'] as List?) ?? [];
    return Container(
      margin: const EdgeInsets.fromLTRB(22, 0, 22, 16),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('🟠 用药提醒', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFFFB8C00))),
          const SizedBox(height: 12),
          for (final m in items)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('💊 ${m['name']}（${m['schedule']}）', style: const TextStyle(fontSize: 16)),
                  ElevatedButton(
                    onPressed: () {},
                    style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF43A047), foregroundColor: Colors.white),
                    child: const Text('已吃 ✓'),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _safetyCard(Map<String, dynamic> hs) {
    final devices = (hs['devices'] as List?) ?? [];
    return Container(
      margin: const EdgeInsets.fromLTRB(22, 0, 22, 16),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('🩵 居家安全', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF00897B))),
          const SizedBox(height: 12),
          Row(
            children: [
              for (final d in devices)
                Expanded(
                  child: Container(
                    margin: const EdgeInsets.only(right: 8),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: d['abnormal'] == true ? const Color(0xFFFFF3E0) : const Color(0xFFF5FAFD),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${d['type'] == 'emergency_caller' ? '🆘' : '🚨'} ${d['name']}',
                            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                        const SizedBox(height: 4),
                        Text('${d['status'] == 'online' ? '在线' : '离线'} · 电量 ${d['battery']}%',
                            style: TextStyle(fontSize: 13, color: d['abnormal'] == true ? const Color(0xFFC95A1D) : Colors.grey)),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
