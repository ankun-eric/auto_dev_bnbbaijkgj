class CheckupReport {
  final int id;
  final String? reportDate;
  final String? fileUrl;
  final String? thumbnailUrl;
  final String? fileType;
  final int abnormalCount;
  final String status;
  final String? aiAnalysis;
  final Map<String, dynamic>? aiAnalysisJson;
  final List<CheckupIndicator> indicators;
  final String createdAt;
  final double? healthScore;

  CheckupReport({
    required this.id,
    this.reportDate,
    this.fileUrl,
    this.thumbnailUrl,
    this.fileType,
    this.abnormalCount = 0,
    this.status = 'pending',
    this.aiAnalysis,
    this.aiAnalysisJson,
    this.indicators = const [],
    required this.createdAt,
    this.healthScore,
  });

  factory CheckupReport.fromJson(Map<String, dynamic> json) {
    return CheckupReport(
      id: json['id'] ?? 0,
      reportDate: json['report_date'],
      fileUrl: json['file_url'],
      thumbnailUrl: json['thumbnail_url'],
      fileType: json['file_type'],
      abnormalCount: json['abnormal_count'] ?? 0,
      status: json['status'] ?? 'pending',
      aiAnalysis: json['ai_analysis'],
      aiAnalysisJson: json['ai_analysis_json'] is Map<String, dynamic>
          ? json['ai_analysis_json']
          : null,
      indicators: (json['indicators'] as List<dynamic>?)
              ?.map((e) => CheckupIndicator.fromJson(e))
              .toList() ??
          [],
      createdAt: json['created_at'] ?? '',
      healthScore: (json['health_score'] ?? json['healthScore'])?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'report_date': reportDate,
      'file_url': fileUrl,
      'thumbnail_url': thumbnailUrl,
      'file_type': fileType,
      'abnormal_count': abnormalCount,
      'status': status,
      'ai_analysis': aiAnalysis,
      'ai_analysis_json': aiAnalysisJson,
      'indicators': indicators.map((e) => e.toJson()).toList(),
      'created_at': createdAt,
      'health_score': healthScore,
    };
  }
}

class CheckupIndicator {
  final int id;
  final String indicatorName;
  final String? value;
  final String? unit;
  final String? referenceRange;
  final String status;
  final String? category;
  final String? advice;

  CheckupIndicator({
    required this.id,
    required this.indicatorName,
    this.value,
    this.unit,
    this.referenceRange,
    this.status = 'normal',
    this.category,
    this.advice,
  });

  factory CheckupIndicator.fromJson(Map<String, dynamic> json) {
    return CheckupIndicator(
      id: json['id'] ?? 0,
      indicatorName: json['indicator_name'] ?? '',
      value: json['value']?.toString(),
      unit: json['unit'],
      referenceRange: json['reference_range'],
      status: json['status'] ?? 'normal',
      category: json['category'],
      advice: json['advice'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'indicator_name': indicatorName,
      'value': value,
      'unit': unit,
      'reference_range': referenceRange,
      'status': status,
      'category': category,
      'advice': advice,
    };
  }

  bool get isAbnormal => status == 'abnormal' || status == 'critical' || status == 'high' || status == 'low';
}

class TrendData {
  final String date;
  final double value;
  final String? referenceRange;

  TrendData({
    required this.date,
    required this.value,
    this.referenceRange,
  });

  factory TrendData.fromJson(Map<String, dynamic> json) {
    return TrendData(
      date: json['date'] ?? '',
      value: (json['value'] ?? 0).toDouble(),
      referenceRange: json['reference_range'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'date': date,
      'value': value,
      'reference_range': referenceRange,
    };
  }
}

class ReportAlert {
  final int id;
  final String indicatorName;
  final String alertType;
  final String alertMessage;
  final bool isRead;
  final String createdAt;

  ReportAlert({
    required this.id,
    required this.indicatorName,
    required this.alertType,
    required this.alertMessage,
    this.isRead = false,
    required this.createdAt,
  });

  factory ReportAlert.fromJson(Map<String, dynamic> json) {
    return ReportAlert(
      id: json['id'] ?? 0,
      indicatorName: json['indicator_name'] ?? '',
      alertType: json['alert_type'] ?? '',
      alertMessage: json['alert_message'] ?? '',
      isRead: json['is_read'] ?? false,
      createdAt: json['created_at'] ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'indicator_name': indicatorName,
      'alert_type': alertType,
      'alert_message': alertMessage,
      'is_read': isRead,
      'created_at': createdAt,
    };
  }
}
