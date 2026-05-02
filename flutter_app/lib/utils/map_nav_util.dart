/// [2026-05-01 门店地图能力 PRD v1.0] 地图导航唤起工具
///
/// - Android：通过 url_launcher 探测高德/百度/腾讯/Google Maps 的 scheme 是否能打开
/// - iOS：通过 url_launcher 的 canLaunchUrl 探测 Apple Maps + 高德/百度/腾讯
/// - 调起时统一传递「门店全称 + 详细地址 + 经纬度」
import 'dart:io' show Platform;

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

class MapAppCandidate {
  final String name;
  final String scheme; // 用于 canLaunch 判断
  final String launchUrl; // 实际唤起 URL（含 query）
  final String fallbackWebUrl;

  const MapAppCandidate({
    required this.name,
    required this.scheme,
    required this.launchUrl,
    required this.fallbackWebUrl,
  });
}

class MapNavUtil {
  /// 构建当前平台支持的所有候选地图 App。
  static List<MapAppCandidate> buildCandidates({
    required String name,
    required String address,
    required double lat,
    required double lng,
  }) {
    final encName = Uri.encodeComponent(name);
    final encAddr = Uri.encodeComponent(address.isEmpty ? name : address);

    final amapIos = 'iosamap://navi?sourceApplication=binihealth&poiname=$encName&lat=$lat&lon=$lng&dev=0&style=2';
    final amapAndroid = 'androidamap://navi?sourceApplication=binihealth&poiname=$encName&lat=$lat&lon=$lng&dev=0&style=2';
    final amap = MapAppCandidate(
      name: '高德地图',
      scheme: Platform.isIOS ? 'iosamap://' : 'androidamap://',
      launchUrl: Platform.isIOS ? amapIos : amapAndroid,
      fallbackWebUrl: 'https://uri.amap.com/marker?position=$lng,$lat&name=$encName&src=binihealth&coordinate=gaode',
    );

    final baidu = MapAppCandidate(
      name: '百度地图',
      scheme: 'baidumap://',
      launchUrl: 'baidumap://map/direction?destination=name:$encName|latlng:$lat,$lng&coord_type=gcj02&mode=driving',
      fallbackWebUrl: 'https://api.map.baidu.com/marker?location=$lat,$lng&title=$encName&content=$encAddr&output=html&coord_type=gcj02&src=binihealth',
    );

    final tencent = MapAppCandidate(
      name: '腾讯地图',
      scheme: 'qqmap://',
      launchUrl: 'qqmap://map/routeplan?type=drive&to=$encName&tocoord=$lat,$lng&referer=binihealth',
      fallbackWebUrl: 'https://apis.map.qq.com/uri/v1/marker?marker=coord:$lat,$lng;title:$encName;addr:$encAddr&referer=binihealth',
    );

    final apple = MapAppCandidate(
      name: 'Apple 地图',
      scheme: 'maps://',
      launchUrl: 'https://maps.apple.com/?q=$encName&ll=$lat,$lng',
      fallbackWebUrl: 'https://maps.apple.com/?q=$encName&ll=$lat,$lng',
    );

    if (Platform.isIOS) {
      return [apple, amap, baidu, tencent];
    }
    return [amap, baidu, tencent];
  }

  /// 探测已安装的 App 列表（按 scheme 是否可唤起）。
  /// 注意：Android 11+ 需要在 AndroidManifest.xml 中声明 <queries>。
  static Future<List<MapAppCandidate>> getInstalled(List<MapAppCandidate> candidates) async {
    final List<MapAppCandidate> installed = [];
    for (final c in candidates) {
      try {
        final ok = await canLaunchUrl(Uri.parse(c.scheme));
        if (ok) installed.add(c);
      } catch (_) {
        // ignore
      }
    }
    return installed;
  }

  static Future<void> launchCandidate(MapAppCandidate c) async {
    final uri = Uri.parse(c.launchUrl);
    bool launched = false;
    try {
      launched = await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      launched = false;
    }
    if (!launched) {
      try {
        await launchUrl(Uri.parse(c.fallbackWebUrl), mode: LaunchMode.externalApplication);
      } catch (_) {
        // ignore
      }
    }
  }

  /// 弹出底部抽屉让用户选择地图 App
  static Future<void> showMapNavSheet(
    BuildContext context, {
    required String name,
    required String address,
    required double lat,
    required double lng,
  }) async {
    final candidates = buildCandidates(name: name, address: address, lat: lat, lng: lng);
    List<MapAppCandidate> installed = await getInstalled(candidates);
    // iOS Apple Maps 始终可用（通过 https:// 兜底），即便 maps:// 不可用也保留
    if (Platform.isIOS && !installed.any((e) => e.name == 'Apple 地图')) {
      installed.insert(0, candidates.firstWhere((e) => e.name == 'Apple 地图'));
    }

    if (installed.isEmpty) {
      // 兜底：显示全部候选 + 提示
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('未检测到已安装的地图 App，将尝试用网页打开')),
      );
      // 直接尝试第一个候选（Web fallback）
      if (candidates.isNotEmpty) {
        await launchCandidate(candidates.first);
      }
      return;
    }

    if (!context.mounted) return;
    await showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
      ),
      builder: (_) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: Text('使用以下地图打开', style: TextStyle(fontWeight: FontWeight.w500)),
                ),
                ...installed.map(
                  (c) => ListTile(
                    title: Text(c.name),
                    leading: const Icon(Icons.map_outlined, color: Colors.green),
                    onTap: () async {
                      Navigator.of(context).pop();
                      await launchCandidate(c);
                    },
                  ),
                ),
                const Divider(height: 1),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('取消', style: TextStyle(color: Color(0xFF999999))),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
