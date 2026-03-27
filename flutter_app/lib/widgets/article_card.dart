import 'package:flutter/material.dart';
import '../models/article.dart';

class ArticleCard extends StatelessWidget {
  final Article article;
  final VoidCallback? onTap;

  const ArticleCard({super.key, required this.article, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.04),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      article.title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        height: 1.3,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 8),
                    if (article.summary != null)
                      Text(
                        article.summary!,
                        style: TextStyle(fontSize: 13, color: Colors.grey[600], height: 1.4),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        if (article.author != null) ...[
                          Icon(Icons.person_outline, size: 14, color: Colors.grey[400]),
                          const SizedBox(width: 2),
                          Text(
                            article.author!,
                            style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                          ),
                          const SizedBox(width: 12),
                        ],
                        Icon(Icons.visibility_outlined, size: 14, color: Colors.grey[400]),
                        const SizedBox(width: 2),
                        Text(
                          '${article.viewCount}',
                          style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              if (article.coverImage != null) ...[
                const SizedBox(width: 12),
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: Container(
                    width: 90,
                    height: 70,
                    color: const Color(0xFFE8F5E9),
                    child: Image.network(article.coverImage!, fit: BoxFit.cover),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
