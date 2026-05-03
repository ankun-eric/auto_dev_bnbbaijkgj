import 'dart:async';
import 'package:flutter/material.dart';
import '../../services/cards_v2_service.dart';

/// 卡核销码屏幕（v2.0 第 3 期）
class RedeemCodeScreen extends StatefulWidget {
  final int userCardId;
  const RedeemCodeScreen({super.key, required this.userCardId});

  @override
  State<RedeemCodeScreen> createState() => _RedeemCodeScreenState();
}

class _RedeemCodeScreenState extends State<RedeemCodeScreen> {
  final _service = CardsV2Service();
  Map<String, dynamic>? _code;
  Timer? _timer;
  int _remaining = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _issue();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _issue() async {
    setState(() => _loading = true);
    try {
      final c = await _service.issueRedemptionCode(widget.userCardId);
      setState(() {
        _code = c;
        _loading = false;
      });
      _startCountdown();
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  void _startCountdown() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_code == null) return;
      final exp = DateTime.parse(_code!['expires_at']).millisecondsSinceEpoch;
      final left = ((exp - DateTime.now().millisecondsSinceEpoch) / 1000).floor();
      setState(() => _remaining = left > 0 ? left : 0);
      if (left <= 0) _issue();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('卡核销码')),
      body: Center(
        child: _loading && _code == null
            ? const CircularProgressIndicator()
            : _code == null
                ? const Text('无可用核销码')
                : Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Container(
                          width: 220,
                          height: 220,
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.green, width: 3),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          padding: const EdgeInsets.all(12),
                          child: Center(
                            child: Text(_code!['token'] ?? '',
                                style: const TextStyle(fontSize: 11), textAlign: TextAlign.center),
                          ),
                        ),
                        const SizedBox(height: 24),
                        Text(_code!['digits'] ?? '',
                            style: const TextStyle(
                                fontSize: 40, letterSpacing: 6, fontFamily: 'monospace')),
                        const SizedBox(height: 12),
                        Text('动态码 · 剩余 $_remaining 秒'),
                        const SizedBox(height: 24),
                        ElevatedButton(onPressed: _issue, child: const Text('立即刷新')),
                      ],
                    ),
                  ),
      ),
    );
  }
}
