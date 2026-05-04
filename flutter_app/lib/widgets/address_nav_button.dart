/// [2026-05-05 订单页地址导航按钮 PRD v1.0] 通用「导航」按钮
///
/// 用于下单页（checkout）/ 订单详情页（order detail）等地址展示行的右侧。
/// 视觉：胶囊形 + 绿色 #52c41a，复用商家详情页同款风格。
///
/// 行为：
///   - 点击后调用 [MapNavUtil.showMapNavSheet]
///   - 有经纬度 → 直接路线规划
///   - 无经纬度 → 关键词搜索路径规划（PRD F-08 降级）
///   - 500ms 防抖（PRD E-09）
import 'package:flutter/material.dart';

import '../utils/map_nav_util.dart';

class AddressNavButton extends StatefulWidget {
  final String name;
  final String address;
  final double? lat;
  final double? lng;
  final EdgeInsetsGeometry? padding;
  final String? semanticLabel;

  const AddressNavButton({
    super.key,
    required this.name,
    required this.address,
    this.lat,
    this.lng,
    this.padding,
    this.semanticLabel,
  });

  @override
  State<AddressNavButton> createState() => _AddressNavButtonState();
}

class _AddressNavButtonState extends State<AddressNavButton> {
  DateTime _lastClick = DateTime.fromMillisecondsSinceEpoch(0);

  Future<void> _onTap() async {
    final now = DateTime.now();
    if (now.difference(_lastClick).inMilliseconds < 500) return;
    _lastClick = now;

    if ((widget.name.trim().isEmpty) && (widget.address.trim().isEmpty)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('地址信息缺失')),
      );
      return;
    }

    await MapNavUtil.showMapNavSheet(
      context,
      name: widget.name.isEmpty ? '目的地' : widget.name,
      address: widget.address,
      lat: widget.lat,
      lng: widget.lng,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: widget.semanticLabel ?? '导航',
      child: GestureDetector(
        onTap: _onTap,
        behavior: HitTestBehavior.opaque,
        child: Container(
          padding: widget.padding ??
              const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: const Color(0x1452C41A), // #52c41a 12% alpha
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: const [
              Icon(Icons.near_me, size: 14, color: Color(0xFF52C41A)),
              SizedBox(width: 4),
              Text(
                '导航',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF52C41A),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
