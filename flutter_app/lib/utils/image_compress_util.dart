// [2026-04-25 Bug-02] Flutter 端图片压缩工具
//
// 目标：长边 ≤ 1920 px，输出体积 ≤ 1 MB（典型扫描件压缩后 300~800 KB）
// 实现：使用 flutter_image_compress 原生 JPEG 编码（支持质量参数），
// 通过 quality 阶梯（80→70→60→50）逼近目标体积；
// 若压缩后文件不存在或体积反而大于原图，则回退原文件路径。
import 'dart:io';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:flutter_image_compress/flutter_image_compress.dart';
import 'package:path_provider/path_provider.dart';

class CheckupImageCompressor {
  static const int targetMinEdge = 1920;
  static const int targetBytes = 1024 * 1024; // 1 MB
  static const List<int> qualitySteps = [80, 70, 60, 50];

  /// 压缩单张图片；返回压缩后的本地文件路径。
  /// 若压缩失败或压缩后体积反而更大，返回原始路径。
  static Future<String> compress(String srcPath) async {
    if (srcPath.isEmpty) return srcPath;
    final lower = srcPath.toLowerCase();
    if (lower.endsWith('.pdf') || lower.endsWith('.gif')) return srcPath;

    File src;
    int originalSize;
    try {
      src = File(srcPath);
      if (!await src.exists()) return srcPath;
      originalSize = await src.length();
    } catch (_) {
      return srcPath;
    }

    Directory tmpDir;
    try {
      tmpDir = await getTemporaryDirectory();
    } catch (_) {
      tmpDir = Directory.systemTemp;
    }

    final rand = Random().nextInt(1 << 32).toRadixString(16);
    final ts = DateTime.now().microsecondsSinceEpoch;
    String? bestPath;
    int bestSize = originalSize;
    int? usedQuality;

    for (final q in qualitySteps) {
      final outPath = '${tmpDir.path}/checkup_compressed_${ts}_${q}_$rand.jpg';
      try {
        final result = await FlutterImageCompress.compressAndGetFile(
          srcPath,
          outPath,
          quality: q,
          minWidth: targetMinEdge,
          minHeight: targetMinEdge,
          format: CompressFormat.jpeg,
        );
        if (result == null) continue;
        final outFile = File(result.path);
        if (!await outFile.exists()) continue;
        final outSize = await outFile.length();
        if (outSize <= 0) continue;

        if (outSize < bestSize) {
          if (bestPath != null) {
            try { await File(bestPath).delete(); } catch (_) {}
          }
          bestPath = result.path;
          bestSize = outSize;
          usedQuality = q;
        } else {
          try { await outFile.delete(); } catch (_) {}
        }

        if (outSize <= targetBytes) {
          break;
        }
      } catch (e) {
        debugPrint('[CheckupImageCompressor] q=$q error: $e');
        continue;
      }
    }

    if (bestPath == null || bestSize >= originalSize) {
      debugPrint(
          '[CheckupImageCompressor] fallback original | src=$srcPath origSize=$originalSize bestSize=$bestSize');
      if (bestPath != null) {
        try { await File(bestPath).delete(); } catch (_) {}
      }
      return srcPath;
    }

    debugPrint(
        '[CheckupImageCompressor] OK | src=$srcPath origSize=$originalSize -> $bestSize bytes (quality=$usedQuality)');
    return bestPath;
  }

  static Future<List<String>> compressAll(List<String> paths) async {
    final out = <String>[];
    for (final p in paths) {
      try {
        out.add(await compress(p));
      } catch (_) {
        out.add(p);
      }
    }
    return out;
  }
}
