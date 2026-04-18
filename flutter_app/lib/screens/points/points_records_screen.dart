import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class PointsRecordsScreen extends StatefulWidget {
  const PointsRecordsScreen({super.key});

  @override
  State<PointsRecordsScreen> createState() => _PointsRecordsScreenState();
}

class _PointsRecordsScreenState extends State<PointsRecordsScreen> {
  final ApiService _api = ApiService();
  final ScrollController _scrollCtrl = ScrollController();
  final List<Map<String, dynamic>> _records = [];
  int _page = 1;
  bool _loading = false;
  bool _noMore = false;

  static const _typeLabel = {
    'signin': '每日签到',
    'checkin': '健康打卡',
    'completeProfile': '完善档案',
    'invite': '邀请奖励',
    'firstOrder': '首次下单',
    'reviewService': '订单评价',
    'exchange': '积分兑换',
    'consume': '积分消费',
  };

  @override
  void initState() {
    super.initState();
    _loadMore();
    _scrollCtrl.addListener(() {
      if (_scrollCtrl.position.pixels >= _scrollCtrl.position.maxScrollExtent - 80) {
        _loadMore();
      }
    });
  }

  @override
  void dispose() {
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadMore() async {
    if (_loading || _noMore) return;
    setState(() => _loading = true);
    try {
      final res = await _api.getPointsRecords(page: _page);
      final data = res.data is Map ? res.data as Map : {};
      final items = (data['items'] ?? data['records'] ?? []) as List;
      setState(() {
        _records.addAll(items.map((e) => Map<String, dynamic>.from(e as Map)));
        _page++;
        _noMore = items.length < 20;
      });
    } catch (_) {
      setState(() => _noMore = true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F5F5),
      appBar: AppBar(title: const Text('积分明细'), backgroundColor: const Color(0xFF52C41A)),
      body: _records.isEmpty && !_loading
          ? const Center(child: Text('暂无积分记录', style: TextStyle(color: Colors.grey)))
          : ListView.builder(
              controller: _scrollCtrl,
              itemCount: _records.length + 1,
              itemBuilder: (context, index) {
                if (index == _records.length) {
                  if (_loading) return const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator(color: Color(0xFF52C41A))));
                  if (_noMore && _records.isNotEmpty) return const Padding(padding: EdgeInsets.all(16), child: Center(child: Text('— 没有更多了 —', style: TextStyle(color: Colors.grey, fontSize: 12))));
                  return const SizedBox.shrink();
                }
                final r = _records[index];
                final pts = r['points'] ?? 0;
                final isIncome = pts >= 0;
                final type = r['type']?.toString() ?? '';
                final label = _typeLabel[type] ?? type;
                final time = (r['created_at']?.toString() ?? '').replaceAll('T', ' ');
                return Container(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(10)),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(r['description']?.toString() ?? label, style: const TextStyle(fontSize: 14)),
                            const SizedBox(height: 4),
                            Text(time.length >= 19 ? time.substring(0, 19) : time, style: const TextStyle(fontSize: 11, color: Colors.grey)),
                          ],
                        ),
                      ),
                      Text(
                        '${isIncome ? '+' : ''}$pts',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: isIncome ? const Color(0xFF52C41A) : Colors.red),
                      ),
                    ],
                  ),
                );
              },
            ),
    );
  }
}
