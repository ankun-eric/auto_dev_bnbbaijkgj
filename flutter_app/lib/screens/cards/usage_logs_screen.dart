import 'package:flutter/material.dart';
import '../../services/cards_v2_service.dart';

class UsageLogsScreen extends StatefulWidget {
  final int userCardId;
  const UsageLogsScreen({super.key, required this.userCardId});

  @override
  State<UsageLogsScreen> createState() => _UsageLogsScreenState();
}

class _UsageLogsScreenState extends State<UsageLogsScreen> {
  final _service = CardsV2Service();
  List<dynamic> _items = [];
  int _total = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final r = await _service.myUsageLogs(widget.userCardId);
      setState(() {
        _items = r['items'] ?? [];
        _total = r['total'] ?? 0;
        _loading = false;
      });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('核销记录（共 $_total 条）')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? const Center(child: Text('暂无核销记录'))
              : ListView.separated(
                  itemCount: _items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (_, i) {
                    final it = _items[i];
                    return ListTile(
                      title: Text(it['product_name'] ?? '商品#${it['product_id']}'),
                      subtitle: Text(
                          '${it['store_name'] ?? '门店#${it['store_id'] ?? '-'}'} · ${it['used_at'] ?? ''}'),
                    );
                  },
                ),
    );
  }
}
