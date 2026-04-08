class HealthScoreInfo {
  final double score;
  final String level;
  final String comment;

  HealthScoreInfo({
    required this.score,
    required this.level,
    required this.comment,
  });

  factory HealthScoreInfo.fromJson(Map<String, dynamic> json) {
    return HealthScoreInfo(
      score: (json['score'] ?? 0).toDouble(),
      level: json['level']?.toString() ?? '',
      comment: json['comment']?.toString() ?? '',
    );
  }
}

class SummaryInfo {
  final int totalItems;
  final int abnormalCount;
  final int excellentCount;
  final int normalCount;

  SummaryInfo({
    required this.totalItems,
    required this.abnormalCount,
    required this.excellentCount,
    required this.normalCount,
  });

  factory SummaryInfo.fromJson(Map<String, dynamic> json) {
    return SummaryInfo(
      totalItems: json['totalItems'] ?? json['total_items'] ?? 0,
      abnormalCount: json['abnormalCount'] ?? json['abnormal_count'] ?? 0,
      excellentCount: json['excellentCount'] ?? json['excellent_count'] ?? 0,
      normalCount: json['normalCount'] ?? json['normal_count'] ?? 0,
    );
  }
}

class IndicatorDetailAdvice {
  final String explanation;
  final String possibleCauses;
  final String dietAdvice;
  final String exerciseAdvice;
  final String lifestyleAdvice;
  final String recheckAdvice;
  final String medicalAdvice;

  IndicatorDetailAdvice({
    required this.explanation,
    required this.possibleCauses,
    required this.dietAdvice,
    required this.exerciseAdvice,
    required this.lifestyleAdvice,
    required this.recheckAdvice,
    required this.medicalAdvice,
  });

  factory IndicatorDetailAdvice.fromJson(Map<String, dynamic> json) {
    return IndicatorDetailAdvice(
      explanation: json['explanation']?.toString() ?? '',
      possibleCauses: json['possibleCauses']?.toString() ?? json['possible_causes']?.toString() ?? '',
      dietAdvice: json['dietAdvice']?.toString() ?? json['diet_advice']?.toString() ?? '',
      exerciseAdvice: json['exerciseAdvice']?.toString() ?? json['exercise_advice']?.toString() ?? '',
      lifestyleAdvice: json['lifestyleAdvice']?.toString() ?? json['lifestyle_advice']?.toString() ?? '',
      recheckAdvice: json['recheckAdvice']?.toString() ?? json['recheck_advice']?.toString() ?? '',
      medicalAdvice: json['medicalAdvice']?.toString() ?? json['medical_advice']?.toString() ?? '',
    );
  }

  List<MapEntry<String, String>> get adviceEntries {
    final entries = <MapEntry<String, String>>[];
    if (explanation.isNotEmpty) entries.add(MapEntry('📋 指标说明', explanation));
    if (possibleCauses.isNotEmpty) entries.add(MapEntry('🔍 可能原因', possibleCauses));
    if (dietAdvice.isNotEmpty) entries.add(MapEntry('🥗 饮食建议', dietAdvice));
    if (exerciseAdvice.isNotEmpty) entries.add(MapEntry('🏃 运动建议', exerciseAdvice));
    if (lifestyleAdvice.isNotEmpty) entries.add(MapEntry('💤 生活方式', lifestyleAdvice));
    if (recheckAdvice.isNotEmpty) entries.add(MapEntry('🔄 复查建议', recheckAdvice));
    if (medicalAdvice.isNotEmpty) entries.add(MapEntry('🏥 就医建议', medicalAdvice));
    return entries;
  }
}

class EnhancedIndicatorItem {
  final String name;
  final String value;
  final String unit;
  final String referenceRange;
  final int riskLevel;
  final String riskName;
  final IndicatorDetailAdvice? detail;

  EnhancedIndicatorItem({
    required this.name,
    required this.value,
    required this.unit,
    required this.referenceRange,
    required this.riskLevel,
    required this.riskName,
    this.detail,
  });

  factory EnhancedIndicatorItem.fromJson(Map<String, dynamic> json) {
    return EnhancedIndicatorItem(
      name: json['name']?.toString() ?? '',
      value: json['value']?.toString() ?? '',
      unit: json['unit']?.toString() ?? '',
      referenceRange: json['referenceRange']?.toString() ?? json['reference_range']?.toString() ?? '',
      riskLevel: json['riskLevel'] ?? json['risk_level'] ?? 2,
      riskName: json['riskName']?.toString() ?? json['risk_name']?.toString() ?? '正常',
      detail: json['detail'] is Map<String, dynamic>
          ? IndicatorDetailAdvice.fromJson(json['detail'])
          : null,
    );
  }

  bool get isAbnormal => riskLevel >= 3;
}

class EnhancedCategory {
  final String name;
  final String emoji;
  final List<EnhancedIndicatorItem> items;

  EnhancedCategory({
    required this.name,
    required this.emoji,
    required this.items,
  });

  factory EnhancedCategory.fromJson(Map<String, dynamic> json) {
    return EnhancedCategory(
      name: json['name']?.toString() ?? '',
      emoji: json['emoji']?.toString() ?? '📊',
      items: (json['items'] as List<dynamic>?)
              ?.map((e) => EnhancedIndicatorItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

  int get abnormalCount => items.where((i) => i.isAbnormal).length;
}

class EnhancedReportAnalysis {
  final int? reportId;
  final String? status;
  final HealthScoreInfo? healthScore;
  final SummaryInfo? summary;
  final List<EnhancedCategory> categories;
  final String? disclaimer;

  EnhancedReportAnalysis({
    this.reportId,
    this.status,
    this.healthScore,
    this.summary,
    required this.categories,
    this.disclaimer,
  });

  factory EnhancedReportAnalysis.fromJson(Map<String, dynamic> json) {
    return EnhancedReportAnalysis(
      reportId: json['reportId'] ?? json['report_id'],
      status: json['status']?.toString(),
      healthScore: json['healthScore'] is Map<String, dynamic>
          ? HealthScoreInfo.fromJson(json['healthScore'])
          : (json['health_score'] is Map<String, dynamic>
              ? HealthScoreInfo.fromJson(json['health_score'])
              : null),
      summary: json['summary'] is Map<String, dynamic>
          ? SummaryInfo.fromJson(json['summary'])
          : null,
      categories: (json['categories'] as List<dynamic>?)
              ?.map((e) => EnhancedCategory.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      disclaimer: json['disclaimer']?.toString(),
    );
  }

  List<EnhancedIndicatorItem> get allAbnormalItems {
    final result = <EnhancedIndicatorItem>[];
    for (final cat in categories) {
      for (final item in cat.items) {
        if (item.isAbnormal) result.add(item);
      }
    }
    return result;
  }
}

class CompareIndicatorItem {
  final String name;
  final String previousValue;
  final String currentValue;
  final String unit;
  final String change;
  final String direction;
  final int previousRiskLevel;
  final int currentRiskLevel;
  final String suggestion;

  CompareIndicatorItem({
    required this.name,
    required this.previousValue,
    required this.currentValue,
    required this.unit,
    required this.change,
    required this.direction,
    required this.previousRiskLevel,
    required this.currentRiskLevel,
    required this.suggestion,
  });

  factory CompareIndicatorItem.fromJson(Map<String, dynamic> json) {
    return CompareIndicatorItem(
      name: json['name']?.toString() ?? '',
      previousValue: json['previousValue']?.toString() ?? json['previous_value']?.toString() ?? '',
      currentValue: json['currentValue']?.toString() ?? json['current_value']?.toString() ?? '',
      unit: json['unit']?.toString() ?? '',
      change: json['change']?.toString() ?? '',
      direction: json['direction']?.toString() ?? '',
      previousRiskLevel: json['previousRiskLevel'] ?? json['previous_risk_level'] ?? 2,
      currentRiskLevel: json['currentRiskLevel'] ?? json['current_risk_level'] ?? 2,
      suggestion: json['suggestion']?.toString() ?? '',
    );
  }

  bool get improved => direction == 'better' || direction == 'improved' || direction == '好转';
  bool get worsened => direction == 'worse' || direction == 'worsened' || direction == '恶化';
}

class CompareScoreDiff {
  final double previousScore;
  final double currentScore;
  final double diff;
  final String comment;

  CompareScoreDiff({
    required this.previousScore,
    required this.currentScore,
    required this.diff,
    required this.comment,
  });

  factory CompareScoreDiff.fromJson(Map<String, dynamic> json) {
    return CompareScoreDiff(
      previousScore: (json['previousScore'] ?? json['previous_score'] ?? 0).toDouble(),
      currentScore: (json['currentScore'] ?? json['current_score'] ?? 0).toDouble(),
      diff: (json['diff'] ?? 0).toDouble(),
      comment: json['comment']?.toString() ?? '',
    );
  }
}

class ReportCompareResult {
  final String aiSummary;
  final CompareScoreDiff? scoreDiff;
  final List<CompareIndicatorItem> indicators;
  final String? disclaimer;

  ReportCompareResult({
    required this.aiSummary,
    this.scoreDiff,
    required this.indicators,
    this.disclaimer,
  });

  factory ReportCompareResult.fromJson(Map<String, dynamic> json) {
    return ReportCompareResult(
      aiSummary: json['aiSummary']?.toString() ?? json['ai_summary']?.toString() ?? '',
      scoreDiff: json['scoreDiff'] is Map<String, dynamic>
          ? CompareScoreDiff.fromJson(json['scoreDiff'])
          : (json['score_diff'] is Map<String, dynamic>
              ? CompareScoreDiff.fromJson(json['score_diff'])
              : null),
      indicators: (json['indicators'] as List<dynamic>?)
              ?.map((e) => CompareIndicatorItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      disclaimer: json['disclaimer']?.toString(),
    );
  }
}
