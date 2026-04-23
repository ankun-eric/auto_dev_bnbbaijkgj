import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

/// 药品图片全屏查看器（v1.2）
/// - 右上角 × 关闭
/// - 底部 "图 X/Y" 指示器
/// - 多图 PageView 左右滑动；单图不可滑动
/// - InteractiveViewer 提供 pinch-zoom
class DrugImageViewer extends StatefulWidget {
  final List<String> imageUrls;
  final int initialIndex;

  const DrugImageViewer({
    super.key,
    required this.imageUrls,
    this.initialIndex = 0,
  });

  static Future<void> show(
    BuildContext context, {
    required List<String> imageUrls,
    int initialIndex = 0,
  }) {
    final urls = imageUrls.where((u) => u.isNotEmpty).toList();
    if (urls.isEmpty) return Future.value();
    return Navigator.of(context).push(
      PageRouteBuilder(
        opaque: false,
        barrierColor: Colors.black.withOpacity(0.92),
        pageBuilder: (_, __, ___) => DrugImageViewer(
          imageUrls: urls,
          initialIndex: initialIndex.clamp(0, urls.length - 1),
        ),
      ),
    );
  }

  @override
  State<DrugImageViewer> createState() => _DrugImageViewerState();
}

class _DrugImageViewerState extends State<DrugImageViewer> {
  late final PageController _controller;
  late int _currentIndex;

  @override
  void initState() {
    super.initState();
    _currentIndex = widget.initialIndex;
    _controller = PageController(initialPage: _currentIndex);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final total = widget.imageUrls.length;
    final multi = total > 1;
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Stack(
        children: [
          PageView.builder(
            controller: _controller,
            physics: multi
                ? const ClampingScrollPhysics()
                : const NeverScrollableScrollPhysics(),
            itemCount: total,
            onPageChanged: (i) => setState(() => _currentIndex = i),
            itemBuilder: (_, i) => InteractiveViewer(
              minScale: 1.0,
              maxScale: 4.0,
              child: Center(
                child: CachedNetworkImage(
                  imageUrl: widget.imageUrls[i],
                  fit: BoxFit.contain,
                  placeholder: (_, __) => const SizedBox(
                    width: 40,
                    height: 40,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  ),
                  errorWidget: (_, __, ___) => const Icon(
                    Icons.broken_image,
                    color: Colors.white54,
                    size: 64,
                  ),
                ),
              ),
            ),
          ),
          Positioned(
            top: MediaQuery.of(context).padding.top + 8,
            right: 8,
            child: Material(
              color: Colors.black.withOpacity(0.4),
              shape: const CircleBorder(),
              child: IconButton(
                icon: const Icon(Icons.close, color: Colors.white, size: 28),
                onPressed: () => Navigator.of(context).pop(),
                tooltip: '关闭',
              ),
            ),
          ),
          if (multi)
            Positioned(
              bottom: MediaQuery.of(context).padding.bottom + 24,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.black.withOpacity(0.55),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(
                    '图 ${_currentIndex + 1}/$total',
                    style: const TextStyle(color: Colors.white, fontSize: 14),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
