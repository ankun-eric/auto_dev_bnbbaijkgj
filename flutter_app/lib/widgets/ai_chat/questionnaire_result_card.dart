// [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] 通用问卷结果卡片（AI 侧）
// [PRD-HSC-OPTIM-V3 2026-05-21] 新增 AI 解读状态轮询 + 按钮置灰联动
import 'dart:async';
import 'package:flutter/material.dart';
import 'dart:math' as math;
import '../../services/api_service.dart';

class QuestionnaireResultCard extends StatefulWidget {
  final Map<String, dynamic> payload;
  final VoidCallback? onTapDetail;

  const QuestionnaireResultCard({
    super.key,
    required this.payload,
    this.onTapDetail,
  });

  @override
  State<QuestionnaireResultCard> createState() => _QuestionnaireResultCardState();
}

class _QuestionnaireResultCardState extends State<QuestionnaireResultCard> {
  String _aiStatus = 'done';
  Timer? _pollTimer;
  DateTime? _pollStartedAt;
  final ApiService _api = ApiService();

  Map<String, dynamic> get payload => widget.payload;
  VoidCallback? get onTapDetail => widget.onTapDetail;

  @override
  void initState() {
    super.initState();
    _maybeStartPoll();
  }

  @override
  void didUpdateWidget(covariant QuestionnaireResultCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.payload != widget.payload) {
      _maybeStartPoll();
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  void _maybeStartPoll() {
    final code = (payload['questionnaire_code'] ?? '').toString();
    final aid = payload['answer_id'] ?? payload['result_id'];
    if (code != 'health_self_check' || aid == null) {
      setState(() => _aiStatus = 'done');
      return;
    }
    _pollTimer?.cancel();
    _aiStatus = 'pending';
    _pollStartedAt = DateTime.now();
    Future<void> pollOnce() async {
      try {
        final resp = await _api.dio.get('/api/questionnaire/answers/$aid/ai-status');
        final data = resp.data is Map ? resp.data as Map : <String, dynamic>{};
        final s = (data['ai_status'] ?? 'done').toString();
        if (!mounted) return;
        setState(() => _aiStatus = s);
        if (s != 'pending') {
          _pollTimer?.cancel();
        }
        if (_pollStartedAt != null &&
            DateTime.now().difference(_pollStartedAt!).inSeconds > 60) {
          _pollTimer?.cancel();
          if (_aiStatus == 'pending') setState(() => _aiStatus = 'failed');
        }
      } catch (_) {
        /* ignore */
      }
    }

    pollOnce();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) => pollOnce());
  }

  Future<void> _retryAi() async {
    final aid = payload['answer_id'] ?? payload['result_id'];
    if (aid == null) return;
    try {
      await _api.dio.post('/api/questionnaire/answers/$aid/retry-ai', data: {});
      _maybeStartPoll();
    } catch (_) {
      /* ignore */
    }
  }

  Color _parseColor(String? hex, Color fallback) {
    if (hex == null || hex.isEmpty) return fallback;
    final h = hex.replaceAll('#', '');
    if (h.length == 6) {
      return Color(int.parse('FF$h', radix: 16));
    }
    if (h.length == 8) {
      return Color(int.parse(h, radix: 16));
    }
    return fallback;
  }

  String _fmtDateTime(String? iso) {
    if (iso == null || iso.isEmpty) return '';
    try {
      final dt = DateTime.parse(iso).toLocal();
      String pad(int v) => v.toString().padLeft(2, '0');
      return '${pad(dt.month)}-${pad(dt.day)} ${pad(dt.hour)}:${pad(dt.minute)}';
    } catch (_) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    final coverColor = _parseColor(payload['cover_color'] as String?, const Color(0xFF0EA5E9));
    final mainType = (payload['main_type'] ?? payload['classification_name'] ?? payload['questionnaire_name'] ?? '结果').toString();
    final secondary = (payload['secondary_types'] as List?)?.cast<dynamic>().map((e) => e.toString()).toList() ?? [];
    final subject = (payload['subject_name'] ?? '').toString();
    final desc = (payload['main_type_desc'] ?? '').toString();
    final scores = (payload['scores'] as Map?)?.map(
          (k, v) => MapEntry(k.toString(), (v is num) ? v.toDouble() : double.tryParse(v.toString()) ?? 0),
        ) ??
        <String, double>{};
    final completedAt = _fmtDateTime(payload['completed_at'] as String?);
    final qnName = (payload['questionnaire_name'] ?? '测评结果').toString();
    final icon = (payload['icon'] ?? '📝').toString();

    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(maxWidth: 380),
      margin: const EdgeInsets.only(top: 4),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFEEF2F7), width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 顶部色带
          Container(
            height: 6,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [coverColor, coverColor.withOpacity(0.5)],
              ),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(14),
                topRight: Radius.circular(14),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        '$icon $qnName',
                        style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (completedAt.isNotEmpty)
                      Text(
                        completedAt,
                        style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
                      ),
                  ],
                ),
                if (subject.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      '被测人：$subject',
                      style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                    ),
                  ),
                Padding(
                  padding: const EdgeInsets.only(top: 6, bottom: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                        decoration: BoxDecoration(
                          color: coverColor.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          '主：$mainType',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: coverColor,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      if (secondary.isNotEmpty)
                        Expanded(
                          child: Text(
                            '兼：${secondary.join('、')}',
                            style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                    ],
                  ),
                ),
                if (desc.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(
                      desc,
                      style: const TextStyle(fontSize: 12, color: Color(0xFF475569), height: 1.5),
                    ),
                  ),
                if (scores.isNotEmpty)
                  SizedBox(
                    height: 180,
                    child: CustomPaint(
                      painter: _RadarPainter(scores: scores, color: coverColor),
                    ),
                  ),
              ],
            ),
          ),
          // [PRD-HSC-OPTIM-V3 2026-05-21] 按 aiStatus 联动「查看详情」按钮
          _buildDetailButton(coverColor),
        ],
      ),
    );
  }

  Widget _buildDetailButton(Color coverColor) {
    if (_aiStatus == 'pending') {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: const BoxDecoration(
          color: Color(0xFFF1F5F9),
          border: Border(top: BorderSide(color: Color(0xFFEEF2F7))),
          borderRadius: BorderRadius.only(
            bottomLeft: Radius.circular(14),
            bottomRight: Radius.circular(14),
          ),
        ),
        child: const Text(
          '分析中...',
          textAlign: TextAlign.center,
          style: TextStyle(
            color: Color(0xFF94A3B8),
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
      );
    }
    if (_aiStatus == 'failed') {
      return Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _retryAi,
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: const BoxDecoration(
              color: Color(0xFFFEF2F2),
              border: Border(top: BorderSide(color: Color(0xFFEEF2F7))),
              borderRadius: BorderRadius.only(
                bottomLeft: Radius.circular(14),
                bottomRight: Radius.circular(14),
              ),
            ),
            child: const Text(
              '重试解读',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Color(0xFFDC2626),
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      );
    }
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTapDetail,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: const BoxDecoration(
            color: Color(0xFFF8FAFC),
            border: Border(top: BorderSide(color: Color(0xFFEEF2F7))),
            borderRadius: BorderRadius.only(
              bottomLeft: Radius.circular(14),
              bottomRight: Radius.circular(14),
            ),
          ),
          child: Text(
            '查看详情 ›',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: coverColor,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ),
    );
  }
}

class _RadarPainter extends CustomPainter {
  final Map<String, double> scores;
  final Color color;

  _RadarPainter({required this.scores, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final labels = scores.keys.toList();
    if (labels.isEmpty) return;
    final cx = size.width / 2;
    final cy = size.height / 2;
    final radius = math.min(size.width, size.height) * 0.36;
    const maxScore = 100.0;
    final angleStep = (math.pi * 2) / labels.length;

    final ringPaint = Paint()
      ..color = const Color(0xFFE5E7EB)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    for (final p in [0.33, 0.66, 1.0]) {
      canvas.drawCircle(Offset(cx, cy), radius * p, ringPaint);
    }
    final axisPaint = Paint()
      ..color = const Color(0xFFE5E7EB)
      ..strokeWidth = 1;
    final path = Path();
    for (int i = 0; i < labels.length; i++) {
      final a = -math.pi / 2 + i * angleStep;
      final ax = cx + math.cos(a) * radius;
      final ay = cy + math.sin(a) * radius;
      canvas.drawLine(Offset(cx, cy), Offset(ax, ay), axisPaint);
      final v = math.max(0.0, math.min(maxScore, scores[labels[i]] ?? 0));
      final r = (v / maxScore) * radius;
      final px = cx + math.cos(a) * r;
      final py = cy + math.sin(a) * r;
      if (i == 0) {
        path.moveTo(px, py);
      } else {
        path.lineTo(px, py);
      }
    }
    path.close();
    final fillPaint = Paint()
      ..color = color.withOpacity(0.2)
      ..style = PaintingStyle.fill;
    final strokePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;
    canvas.drawPath(path, fillPaint);
    canvas.drawPath(path, strokePaint);

    final tp = TextPainter(
      textDirection: TextDirection.ltr,
      maxLines: 1,
    );
    for (int i = 0; i < labels.length; i++) {
      final a = -math.pi / 2 + i * angleStep;
      final lx = cx + math.cos(a) * (radius + 14);
      final ly = cy + math.sin(a) * (radius + 14);
      tp.text = TextSpan(
        text: labels[i],
        style: const TextStyle(fontSize: 9, color: Color(0xFF666666)),
      );
      tp.layout();
      tp.paint(canvas, Offset(lx - tp.width / 2, ly - tp.height / 2));
    }
  }

  @override
  bool shouldRepaint(covariant _RadarPainter old) =>
      old.scores != scores || old.color != color;
}
