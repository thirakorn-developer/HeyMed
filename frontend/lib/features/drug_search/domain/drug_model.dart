import 'package:freezed_annotation/freezed_annotation.dart';

part 'drug_model.freezed.dart';
part 'drug_model.g.dart';

@freezed
class DrugConcept with _$DrugConcept {
  const factory DrugConcept({
    required int rxcui,
    required String tty,
    required String name,
  }) = _DrugConcept;

  factory DrugConcept.fromJson(Map<String, dynamic> json) => _$DrugConceptFromJson(json);
}

@freezed
class DrugDetail with _$DrugDetail {
  const factory DrugDetail({
    required int rxcui,
    required String tty,
    required String name,
    @Default([]) List<DrugConcept> ingredients,
    @JsonKey(name: 'dose_forms') @Default([]) List<DrugConcept> doseForms,
    @Default([]) List<DrugConcept> brands,
    @Default([]) List<DrugConcept> generics,
    @Default([]) List<String> strengths,
    @JsonKey(name: 'ndc_codes') @Default([]) List<String> ndcCodes,
  }) = _DrugDetail;

  factory DrugDetail.fromJson(Map<String, dynamic> json) => _$DrugDetailFromJson(json);
}

@freezed
class DrugSearchResponse with _$DrugSearchResponse {
  const factory DrugSearchResponse({
    required List<DrugConcept> results,
    required int total,
    required String query,
  }) = _DrugSearchResponse;

  factory DrugSearchResponse.fromJson(Map<String, dynamic> json) =>
      _$DrugSearchResponseFromJson(json);
}
