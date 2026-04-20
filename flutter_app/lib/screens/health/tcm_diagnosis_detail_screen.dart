import 'package:flutter/material.dart';
import 'constitution_result_screen.dart';

/// [已废弃] TCM 体质诊断详情页
/// 根据《中医养生 · 体质测评功能优化 PRD v1.0》§ 1.4，
/// 所有测评记录详情统一跳转到 ConstitutionResultScreen（测评结果六屏详情），
/// 本页仅作为兼容路由 `/tcm-diagnosis-detail` 使用，自动重定向。
class TcmDiagnosisDetailScreen extends StatefulWidget {
  const TcmDiagnosisDetailScreen({super.key});

  @override
  State<TcmDiagnosisDetailScreen> createState() => _TcmDiagnosisDetailScreenState();
}

class _TcmDiagnosisDetailScreenState extends State<TcmDiagnosisDetailScreen> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final args = ModalRoute.of(context)?.settings.arguments;
      int? id;
      if (args is Map) {
        final raw = args['id'] ?? args['diagnosis_id'];
        if (raw is int) id = raw;
        if (raw is String) id = int.tryParse(raw);
      }
      if (id != null && id > 0) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => ConstitutionResultScreen(diagnosisId: id!)),
        );
      } else {
        Navigator.pop(context);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator(color: Color(0xFF52C41A))),
    );
  }
}
