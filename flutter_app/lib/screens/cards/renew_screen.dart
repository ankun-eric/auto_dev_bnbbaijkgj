import 'package:flutter/material.dart';
import '../../services/cards_v2_service.dart';

class RenewScreen extends StatefulWidget {
  final int userCardId;
  const RenewScreen({super.key, required this.userCardId});

  @override
  State<RenewScreen> createState() => _RenewScreenState();
}

class _RenewScreenState extends State<RenewScreen> {
  final _service = CardsV2Service();
  bool _submitting = false;

  Future<void> _renew() async {
    setState(() => _submitting = true);
    try {
      final res = await _service.renewCard(widget.userCardId);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('续卡订单已生成 #${res['order_id']}')));
        Navigator.of(context).pop(res);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('续卡失败：$e')));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('续卡确认')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('续卡策略说明：',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            const Text('· STACK 叠加：剩余次数累加，有效期顺延'),
            const Text('· RESET 重置：发新卡，老卡作废'),
            const Text('· DISABLED：不允许续卡'),
            const SizedBox(height: 32),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _submitting ? null : _renew,
                child: Text(_submitting ? '处理中...' : '生成续卡订单'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
