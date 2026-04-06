import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:fluttertoast/fluttertoast.dart';

import '../models/knowledge_hit.dart';

typedef KnowledgeFeedbackCallback = Future<bool> Function(int hitLogId, String feedback);

/// 知识库命中结果卡片：正文、图片、商品与点赞/点踩。
class KnowledgeCard extends StatefulWidget {
  final KnowledgeHit hit;
  final KnowledgeFeedbackCallback? onFeedback;

  const KnowledgeCard({
    super.key,
    required this.hit,
    this.onFeedback,
  });

  @override
  State<KnowledgeCard> createState() => _KnowledgeCardState();
}

class _KnowledgeCardState extends State<KnowledgeCard> {
  String? _localFeedback;
  bool _submitting = false;

  List<String> _imageUrls() {
    final c = widget.hit.contentJson;
    if (c is Map) {
      final imgs = c['images'] ?? c['image_urls'];
      if (imgs is List) {
        return imgs.map((e) => e.toString()).where((s) => s.isNotEmpty).toList();
      }
      final single = c['image'] ?? c['image_url'] ?? c['cover'];
      if (single is String && single.isNotEmpty) return [single];
    }
    return [];
  }

  String? _bodyText() {
    final c = widget.hit.contentJson;
    if (c == null) return null;
    if (c is String) return c.isEmpty ? null : c;
    if (c is Map) {
      for (final k in ['text', 'body', 'content', 'answer', 'description']) {
        final v = c[k];
        if (v is String && v.trim().isNotEmpty) return v.trim();
      }
    }
    return null;
  }

  List<ProductCard> _products() {
    if (widget.hit.products != null && widget.hit.products!.isNotEmpty) {
      return widget.hit.products!;
    }
    final c = widget.hit.contentJson;
    if (c is Map) {
      final p = c['products'];
      if (p is List) {
        return p
            .map((e) => ProductCard.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList();
      }
    }
    return [];
  }

  void _showImageFullScreen(String url) {
    showDialog<void>(
      context: context,
      barrierColor: Colors.black87,
      builder: (ctx) {
        return Dialog(
          backgroundColor: Colors.transparent,
          insetPadding: EdgeInsets.zero,
          child: Stack(
            fit: StackFit.expand,
            children: [
              Center(
                child: InteractiveViewer(
                  minScale: 0.5,
                  maxScale: 4,
                  child: CachedNetworkImage(
                    imageUrl: url,
                    fit: BoxFit.contain,
                    placeholder: (_, __) => const CircularProgressIndicator(color: Colors.white),
                    errorWidget: (_, __, ___) => const Icon(Icons.broken_image, color: Colors.white, size: 48),
                  ),
                ),
              ),
              Positioned(
                top: MediaQuery.of(ctx).padding.top + 8,
                right: 8,
                child: IconButton(
                  icon: const Icon(Icons.close, color: Colors.white, size: 28),
                  onPressed: () => Navigator.of(ctx).pop(),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _onVote(String feedback) async {
    final id = widget.hit.hitLogId;
    if (id == null) {
      Fluttertoast.showToast(msg: '暂无法反馈，请稍后再试');
      return;
    }
    if (widget.onFeedback == null) return;
    if (_submitting) return;
    setState(() => _submitting = true);
    final ok = await widget.onFeedback!(id, feedback);
    if (!mounted) return;
    setState(() => _submitting = false);
    if (ok) {
      setState(() => _localFeedback = feedback);
      Fluttertoast.showToast(msg: feedback == 'like' ? '感谢反馈' : '已记录您的反馈');
    } else {
      Fluttertoast.showToast(msg: '反馈提交失败，请稍后重试');
    }
  }

  @override
  Widget build(BuildContext context) {
    final body = _bodyText();
    final images = _imageUrls();
    final products = _products();

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 8),
      decoration: BoxDecoration(
        color: const Color(0xFFF7F9FC),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE8ECF2)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: const Color(0xFFE6F7FF),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    '知识库',
                    style: TextStyle(fontSize: 11, color: Color(0xFF1890FF), fontWeight: FontWeight.w600),
                  ),
                ),
                if (widget.hit.kbName.isNotEmpty) ...[
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      widget.hit.kbName,
                      style: TextStyle(fontSize: 12, color: Colors.grey[700]),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ],
            ),
            if (widget.hit.question != null && widget.hit.question!.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                widget.hit.question!,
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
              ),
            ],
            if (widget.hit.title != null &&
                widget.hit.title!.isNotEmpty &&
                widget.hit.title != widget.hit.question) ...[
              const SizedBox(height: 4),
              Text(
                widget.hit.title!,
                style: TextStyle(fontSize: 13, color: Colors.grey[800]),
              ),
            ],
            if (body != null) ...[
              const SizedBox(height: 8),
              Text(
                body,
                style: const TextStyle(fontSize: 14, height: 1.5, color: Color(0xFF333333)),
              ),
            ],
            ...images.map(
              (url) => Padding(
                padding: const EdgeInsets.only(top: 8),
                child: GestureDetector(
                  onTap: () => _showImageFullScreen(url),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: CachedNetworkImage(
                      imageUrl: url,
                      width: double.infinity,
                      height: 160,
                      fit: BoxFit.cover,
                      placeholder: (_, __) => Container(
                        height: 160,
                        color: Colors.grey[200],
                        child: const Center(child: CircularProgressIndicator(strokeWidth: 2)),
                      ),
                      errorWidget: (_, __, ___) => Container(
                        height: 120,
                        color: Colors.grey[200],
                        alignment: Alignment.center,
                        child: const Icon(Icons.image_not_supported_outlined, color: Colors.grey),
                      ),
                    ),
                  ),
                ),
              ),
            ),
            ...products.map(_buildProductRow),
            const SizedBox(height: 8),
            if (widget.hit.matchScore > 0 || widget.hit.matchType.isNotEmpty)
              Row(
                children: [
                  if (widget.hit.matchType.isNotEmpty)
                    Text(
                      widget.hit.matchScore > 0
                          ? '${widget.hit.matchType} · '
                          : widget.hit.matchType,
                      style: TextStyle(fontSize: 11, color: Colors.grey[500]),
                    ),
                  if (widget.hit.matchScore > 0)
                    Text(
                      '匹配度 ${(widget.hit.matchScore * 100).toStringAsFixed(0)}%',
                      style: TextStyle(fontSize: 11, color: Colors.grey[500]),
                    ),
                ],
              ),
            const SizedBox(height: 8),
            Row(
              children: [
                _VoteButton(
                  icon: Icons.thumb_up_outlined,
                  activeIcon: Icons.thumb_up,
                  label: '有用',
                  active: _localFeedback == 'like',
                  activeColor: const Color(0xFF52C41A),
                  disabled: _submitting || widget.hit.hitLogId == null,
                  onTap: () => _onVote('like'),
                ),
                const SizedBox(width: 16),
                _VoteButton(
                  icon: Icons.thumb_down_outlined,
                  activeIcon: Icons.thumb_down,
                  label: '无用',
                  active: _localFeedback == 'dislike',
                  activeColor: const Color(0xFFFF4D4F),
                  disabled: _submitting || widget.hit.hitLogId == null,
                  onTap: () => _onVote('dislike'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProductRow(ProductCard p) {
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFEEEEEE)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: p.image != null && p.image!.isNotEmpty
                ? CachedNetworkImage(
                    imageUrl: p.image!,
                    width: 56,
                    height: 56,
                    fit: BoxFit.cover,
                    errorWidget: (_, __, ___) => _productPlaceholder(),
                  )
                : _productPlaceholder(),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  p.name,
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Text(
                  '¥${p.price.toStringAsFixed(p.price == p.price.roundToDouble() ? 0 : 2)}',
                  style: const TextStyle(fontSize: 15, color: Color(0xFFFF4D4F), fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
          TextButton(
            onPressed: () {
              Fluttertoast.showToast(msg: '商品详情即将开放');
            },
            child: const Text('查看详情', style: TextStyle(fontSize: 13)),
          ),
        ],
      ),
    );
  }

  Widget _productPlaceholder() {
    return Container(
      width: 56,
      height: 56,
      color: Colors.grey[200],
      child: Icon(Icons.inventory_2_outlined, color: Colors.grey[400], size: 28),
    );
  }
}

class _VoteButton extends StatelessWidget {
  final IconData icon;
  final IconData activeIcon;
  final String label;
  final bool active;
  final Color activeColor;
  final bool disabled;
  final VoidCallback onTap;

  const _VoteButton({
    required this.icon,
    required this.activeIcon,
    required this.label,
    required this.active,
    required this.activeColor,
    required this.disabled,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = active ? activeColor : Colors.grey[600];
    return InkWell(
      onTap: disabled ? null : onTap,
      borderRadius: BorderRadius.circular(20),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(active ? activeIcon : icon, size: 18, color: disabled ? Colors.grey[400] : color),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(fontSize: 13, color: disabled ? Colors.grey[400] : color),
            ),
          ],
        ),
      ),
    );
  }
}
