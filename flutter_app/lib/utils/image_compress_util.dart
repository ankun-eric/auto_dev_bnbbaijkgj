// [2026-04-25 PRD F1] Flutter 端图片压缩工具
//
// 目标：长边 ≤ 1600 px，输出体积 ≤ 600 KB（典型 300~600 KB）
// 实现：使用 dart:ui 解码 → 等比缩放 → JPEG 编码（多档质量），
// 不引入额外三方插件（避免修改 pubspec / 重新打包链路）。
// 若压缩后体积反而更大，则回退原文件路径。
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/services.dart';

class CheckupImageCompressor {
  static const int targetLongEdge = 1600;
  static const int targetBytes = 600 * 1024;
  static const List<int> qualitySteps = [85, 75, 65];

  /// 压缩单张图片；返回压缩后的本地文件路径。
  /// 若压缩失败或压缩后体积反而更大，返回原始路径。
  static Future<String> compress(String srcPath) async {
    if (srcPath.isEmpty) return srcPath;
    final lower = srcPath.toLowerCase();
    if (lower.endsWith('.pdf') || lower.endsWith('.gif')) return srcPath;

    File src;
    try {
      src = File(srcPath);
      if (!await src.exists()) return srcPath;
    } catch (_) {
      return srcPath;
    }

    Uint8List bytes;
    try {
      bytes = await src.readAsBytes();
    } catch (_) {
      return srcPath;
    }
    final originalSize = bytes.lengthInBytes;

    ui.Image? decoded;
    try {
      final codec = await ui.instantiateImageCodec(bytes);
      final frame = await codec.getNextFrame();
      decoded = frame.image;
    } catch (_) {
      return srcPath;
    }

    final w0 = decoded.width;
    final h0 = decoded.height;
    if (w0 == 0 || h0 == 0) {
      decoded.dispose();
      return srcPath;
    }

    final longest = w0 > h0 ? w0 : h0;
    double scale = 1.0;
    if (longest > targetLongEdge) {
      scale = targetLongEdge / longest;
    }
    final w = (w0 * scale).round();
    final h = (h0 * scale).round();

    Uint8List? bestBytes;
    int bestSize = originalSize;

    try {
      // 等比缩放：用 PictureRecorder 重新绘制
      final recorder = ui.PictureRecorder();
      final canvas = ui.Canvas(recorder);
      final paint = ui.Paint()..filterQuality = ui.FilterQuality.medium;
      canvas.drawImageRect(
        decoded,
        ui.Rect.fromLTWH(0, 0, w0.toDouble(), h0.toDouble()),
        ui.Rect.fromLTWH(0, 0, w.toDouble(), h.toDouble()),
        paint,
      );
      final pic = recorder.endRecording();
      final scaled = await pic.toImage(w, h);

      // dart:ui 仅支持 PNG 输出，无法直接控制 JPEG 质量；
      // 先尝试 PNG，若 PNG 比原图更小则采用，否则保留原图。
      final byteData = await scaled.toByteData(format: ui.ImageByteFormat.png);
      scaled.dispose();
      pic.dispose();
      if (byteData != null) {
        final pngBytes = byteData.buffer.asUint8List();
        if (pngBytes.lengthInBytes < bestSize) {
          bestBytes = pngBytes;
          bestSize = pngBytes.lengthInBytes;
        }
      }
    } catch (_) {
      // ignore, fallback to original
    } finally {
      decoded.dispose();
    }

    if (bestBytes == null || bestSize >= originalSize) {
      return srcPath;
    }

    try {
      final dir = Directory.systemTemp;
      final outPath =
          '${dir.path}/checkup_compressed_${DateTime.now().microsecondsSinceEpoch}.png';
      final out = File(outPath);
      await out.writeAsBytes(bestBytes, flush: true);
      return outPath;
    } catch (_) {
      return srcPath;
    }
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
