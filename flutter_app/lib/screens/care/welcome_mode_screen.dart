// [PRD-AIHOME-CARE-V1 2026-05-27] Flutter 首次进入版本选择页
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../services/api_service.dart';
import 'care_home_screen.dart';

class WelcomeModeScreen extends StatefulWidget {
  const WelcomeModeScreen({super.key});

  @override
  State<WelcomeModeScreen> createState() => _WelcomeModeScreenState();
}

class _WelcomeModeScreenState extends State<WelcomeModeScreen> {
  bool _submitting = false;

  Future<void> _choose(String mode) async {
    if (_submitting) return;
    setState(() => _submitting = true);
    try {
      await ApiService().dio.put(
        '/api/care-v1/user-preferences/ui-mode',
        data: {'ui_mode': mode, 'first_choice': true},
      );
    } catch (_) {}
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('ui_mode', mode);
    if (!mounted) return;
    if (mode == 'care') {
      Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const CareHomeScreen()));
    } else {
      Navigator.of(context).pop();
    }
  }

  void _skip() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('ui_mode', 'standard');
    if (!mounted) return;
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF5E8),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(22, 32, 22, 60),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Center(
                child: Text('宾尼小康',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: Color(0xFFFF6B3D))),
              ),
              const SizedBox(height: 20),
              const Text('您好，欢迎来到宾尼小康 👋',
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: Color(0xFF3D2E1F))),
              const SizedBox(height: 8),
              const Text(
                '为了让您用得更顺手，请先选择一种使用模式。选完之后，随时可在首页右上角切换。',
                style: TextStyle(fontSize: 16, color: Color(0xFF5A4838), height: 1.6),
              ),
              const SizedBox(height: 28),
              _modeCard(
                onTap: () => _choose('care'),
                title: '关怀模式',
                icon: '👵',
                border: const Color(0xFFFF9156),
                titleColor: const Color(0xFF3D2E1F),
                showRecommend: true,
                desc: '为长辈量身打造：字更大、按钮更大、语音优先。小康会主动关心您的健康，关键时刻一键求救，让您和家人都安心。',
                tags: const ['超大字', '超大按钮', '语音优先', 'AI 主动关怀', 'SOS 一键求救'],
                tagBg: const Color(0xFFFFF5E8),
                tagColor: const Color(0xFFC95A1D),
              ),
              const SizedBox(height: 18),
              _modeCard(
                onTap: () => _choose('standard'),
                title: '标准模式',
                icon: '🧑‍💼',
                border: const Color(0xFF5B8FD6),
                titleColor: const Color(0xFF2A3A52),
                showRecommend: false,
                desc: '为熟悉手机操作的用户准备：常规字号、功能完整、数据可视化更丰富，适合自己管理健康或帮长辈打理档案的子女使用。',
                tags: const ['常规字号', '功能更全', '操作更高效', '数据可视化'],
                tagBg: const Color(0xFFE8F0FB),
                tagColor: const Color(0xFF3865A8),
              ),
              const SizedBox(height: 18),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(color: const Color(0xFFFFF5E8), borderRadius: BorderRadius.circular(14)),
                child: const Text(
                  '💡 小康的建议：如果您觉得手机操作有些吃力，或者想给长辈使用，推荐选择「关怀模式」。',
                  style: TextStyle(fontSize: 14, color: Color(0xFFC95A1D), height: 1.6),
                ),
              ),
              const SizedBox(height: 24),
              Center(
                child: TextButton(
                  onPressed: _skip,
                  child: const Text('暂不选择，先进去看看 →', style: TextStyle(color: Colors.grey)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _modeCard({
    required VoidCallback onTap,
    required String title,
    required String icon,
    required Color border,
    required Color titleColor,
    required bool showRecommend,
    required String desc,
    required List<String> tags,
    required Color tagBg,
    required Color tagColor,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Stack(
        children: [
          Container(
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: border, width: 2),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(icon, style: const TextStyle(fontSize: 40)),
                    const SizedBox(width: 14),
                    Text(title, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: titleColor)),
                  ],
                ),
                const SizedBox(height: 14),
                Text(desc, style: const TextStyle(fontSize: 16, color: Color(0xFF5A4838), height: 1.7)),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: tags.map((t) => Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                    decoration: BoxDecoration(color: tagBg, borderRadius: BorderRadius.circular(16)),
                    child: Text(t, style: TextStyle(fontSize: 13, color: tagColor, fontWeight: FontWeight.w600)),
                  )).toList(),
                ),
              ],
            ),
          ),
          if (showRecommend)
            Positioned(
              top: 14,
              right: 14,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(colors: [Color(0xFFFF9156), Color(0xFFFF6B3D)]),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Text('⭐ 推荐', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700)),
              ),
            ),
        ],
      ),
    );
  }
}
