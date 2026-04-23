import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import 'drug_image_viewer.dart';

/// 融合卡片平铺（v1.2）
/// 左40% 药图（单药 1 张 / 双药并排），右60% 成员信息 + 药名列表。
/// 不再使用 PageView/Carousel 轮播。
class DrugMergeCardFlat extends StatelessWidget {
  final List<DrugCardItem> drugs;
  final String memberName;
  final int? memberAge;
  final String? memberRelation;

  const DrugMergeCardFlat({
    super.key,
    required this.drugs,
    required this.memberName,
    this.memberAge,
    this.memberRelation,
  });

  String get _relationSuffix =>
      (memberRelation != null && memberRelation!.isNotEmpty && memberRelation != '本人')
          ? ' · $memberRelation'
          : '';

  static const _kTextDark = Color(0xFF333333);
  static const _kBorder = Color(0xFFE8E8E8);

  @override
  Widget build(BuildContext context) {
    if (drugs.isEmpty) return const SizedBox.shrink();
    final visibleDrugs = drugs.take(2).toList();
    final imageUrls = visibleDrugs
        .map((d) => d.imageUrl ?? '')
        .where((u) => u.isNotEmpty)
        .toList();

    return Container(
      height: 160,
      margin: const EdgeInsets.fromLTRB(12, 12, 12, 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(
              flex: 2,
              child: _buildImageArea(context, visibleDrugs, imageUrls),
            ),
            const SizedBox(width: 10),
            Expanded(
              flex: 3,
              child: _buildInfoArea(context, visibleDrugs),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildImageArea(
    BuildContext context,
    List<DrugCardItem> drugs,
    List<String> allUrls,
  ) {
    if (drugs.length == 1) {
      return Center(
        child: GestureDetector(
          onTap: () {
            if (allUrls.isNotEmpty) {
              DrugImageViewer.show(context, imageUrls: allUrls, initialIndex: 0);
            }
          },
          child: _imageBox(
            url: drugs.first.imageUrl,
            width: 140,
            height: 140,
          ),
        ),
      );
    }
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(drugs.length, (i) {
        final d = drugs[i];
        return Flexible(
          child: Padding(
            padding: EdgeInsets.only(right: i == drugs.length - 1 ? 0 : 4),
            child: GestureDetector(
              onTap: () {
                if (allUrls.isNotEmpty) {
                  final idx = d.imageUrl == null
                      ? 0
                      : allUrls.indexOf(d.imageUrl!).clamp(0, allUrls.length - 1);
                  DrugImageViewer.show(
                    context,
                    imageUrls: allUrls,
                    initialIndex: idx,
                  );
                }
              },
              child: _imageBox(url: d.imageUrl, width: 68, height: 140),
            ),
          ),
        );
      }),
    );
  }

  Widget _imageBox({required String? url, required double width, required double height}) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: const Color(0xFFF5F5F5),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade300, width: 1),
      ),
      clipBehavior: Clip.antiAlias,
      child: (url == null || url.isEmpty)
          ? const Center(
              child: Icon(Icons.medication, color: Color(0xFFBBBBBB), size: 40),
            )
          : CachedNetworkImage(
              imageUrl: url,
              fit: BoxFit.cover,
              placeholder: (_, __) => const Center(
                child: SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
              errorWidget: (_, __, ___) => const Center(
                child: Icon(Icons.broken_image, color: Color(0xFFBBBBBB), size: 32),
              ),
            ),
    );
  }

  Widget _buildInfoArea(BuildContext context, List<DrugCardItem> drugs) {
    final ageText = memberAge != null ? ' · ${memberAge}岁' : '';
    final headerTitle = '$memberName$ageText$_relationSuffix';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          children: [
            CircleAvatar(
              radius: 20,
              backgroundColor: const Color(0xFFEB2F96).withOpacity(0.12),
              child: Text(
                (memberName.isNotEmpty ? memberName.substring(0, 1) : '我'),
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFFEB2F96),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                headerTitle,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: _kTextDark,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        const Divider(height: 1, color: _kBorder),
        const SizedBox(height: 6),
        ...drugs.map((d) => _buildDrugRow(context, d)),
      ],
    );
  }

  Widget _buildDrugRow(BuildContext context, DrugCardItem drug) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: GestureDetector(
        onTap: () {
          ScaffoldMessenger.of(context).removeCurrentSnackBar();
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(drug.name),
              duration: const Duration(seconds: 2),
            ),
          );
        },
        child: Row(
          children: [
            const Text('💊 ', style: TextStyle(fontSize: 15)),
            Expanded(
              child: Text(
                drug.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 15,
                  color: _kTextDark,
                  height: 1.3,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class DrugCardItem {
  final int? id;
  final String name;
  final String? imageUrl;

  const DrugCardItem({this.id, required this.name, this.imageUrl});

  factory DrugCardItem.fromJson(Map<String, dynamic> json) {
    return DrugCardItem(
      id: json['id'] is int
          ? json['id'] as int
          : int.tryParse(json['id']?.toString() ?? ''),
      name: json['name']?.toString() ?? '未知药品',
      imageUrl: json['image_url']?.toString(),
    );
  }
}
