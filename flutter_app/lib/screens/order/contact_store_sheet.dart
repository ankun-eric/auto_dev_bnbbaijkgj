import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../services/api_service.dart';

/// [核销订单过期+改期规则优化 v1.0]「联系商家」底部弹窗
///
/// 数据来源严格为 GET /api/stores/{id}/contact（门店管理-联系电话）。
/// 不取商家总部电话；缺字段时按 PRD 异常处理（隐藏拨打/导航按钮）。
class ContactStoreSheet extends StatefulWidget {
  final int? storeId;
  final String? fallbackStoreName;

  const ContactStoreSheet({
    Key? key,
    required this.storeId,
    this.fallbackStoreName,
  }) : super(key: key);

  static Future<void> show(
    BuildContext context, {
    required int? storeId,
    String? fallbackStoreName,
  }) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => ContactStoreSheet(
        storeId: storeId,
        fallbackStoreName: fallbackStoreName,
      ),
    );
  }

  @override
  State<ContactStoreSheet> createState() => _ContactStoreSheetState();
}

class _ContactStoreSheetState extends State<ContactStoreSheet> {
  bool _loading = true;
  Map<String, dynamic>? _info;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (widget.storeId == null) {
      setState(() => _loading = false);
      return;
    }
    try {
      final resp =
          await ApiService().get('/api/stores/${widget.storeId}/contact');
      if (!mounted) return;
      final data = resp.data;
      setState(() {
        _info = data is Map<String, dynamic> ? data : null;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  Future<void> _callPhone(String phone) async {
    final uri = Uri.parse('tel:$phone');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('无法拨打电话')),
      );
    }
  }

  Future<void> _navigate(double lat, double lng, String? name) async {
    final url = Uri.parse(
        'https://uri.amap.com/marker?position=$lng,$lat&name=${Uri.encodeComponent(name ?? "门店")}');
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    final info = _info ?? const {};
    final storeName = (info['store_name']?.toString() ?? '').isNotEmpty
        ? info['store_name'].toString()
        : (widget.fallbackStoreName ?? '门店');
    final address = info['address']?.toString();
    final phone = info['contact_phone']?.toString();
    final lat = (info['lat'] is num) ? (info['lat'] as num).toDouble() : null;
    final lng = (info['lng'] is num) ? (info['lng'] as num).toDouble() : null;

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: const Color(0xFFE5E5E5),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const Text('联系商家',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            if (_loading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Center(child: CircularProgressIndicator()),
              )
            else ...[
              _row(label: '门店', value: storeName),
              if (address != null && address.isNotEmpty)
                _row(
                  label: '地址',
                  value: address,
                  trailing: (lat != null && lng != null)
                      ? _miniBtn('导航', const Color(0xFF52C41A),
                          () => _navigate(lat, lng, storeName))
                      : null,
                ),
              _row(
                label: '联系电话',
                value: (phone != null && phone.isNotEmpty)
                    ? phone
                    : '商家未提供联系方式',
                trailing: (phone != null && phone.isNotEmpty)
                    ? _miniBtn('拨打', const Color(0xFF52C41A),
                        () => _callPhone(phone), filled: true)
                    : null,
              ),
              const SizedBox(height: 12),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                decoration: BoxDecoration(
                  color: const Color(0xFFFAFAFA),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text('如有疑问可联系商家协商处理',
                    style: TextStyle(color: Color(0xFF999999), fontSize: 12)),
              ),
              const SizedBox(height: 16),
              GestureDetector(
                onTap: () => Navigator.of(context).pop(),
                child: Container(
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: const Color(0xFFF5F5F5),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Text('关闭',
                      style: TextStyle(color: Color(0xFF666666))),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _row({required String label, required String value, Widget? trailing}) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: Color(0xFFF0F0F0))),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label,
                    style: const TextStyle(
                        color: Color(0xFF999999), fontSize: 12)),
                const SizedBox(height: 4),
                Text(value,
                    style: const TextStyle(
                        color: Color(0xFF333333),
                        fontSize: 14,
                        fontWeight: FontWeight.w500)),
              ],
            ),
          ),
          if (trailing != null) trailing,
        ],
      ),
    );
  }

  Widget _miniBtn(String text, Color color, VoidCallback onTap,
      {bool filled = false}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(left: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: filled ? color : color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          text,
          style: TextStyle(
            color: filled ? Colors.white : color,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}
