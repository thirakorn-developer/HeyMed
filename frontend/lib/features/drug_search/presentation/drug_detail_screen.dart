import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/drug_api.dart';
import '../domain/drug_model.dart';

final drugDetailProvider = FutureProvider.family<DrugDetail, int>((ref, rxcui) async {
  final api = ref.read(drugApiProvider);
  return api.getDetail(rxcui);
});

class DrugDetailScreen extends ConsumerWidget {
  final int rxcui;

  const DrugDetailScreen({super.key, required this.rxcui});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detailAsync = ref.watch(drugDetailProvider(rxcui));

    return Scaffold(
      appBar: AppBar(title: const Text('Drug Detail')),
      body: detailAsync.when(
        data: (detail) => _DrugDetailBody(detail: detail),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Error: $e')),
      ),
    );
  }
}

class _DrugDetailBody extends StatelessWidget {
  final DrugDetail detail;

  const _DrugDetailBody({required this.detail});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(detail.name, style: theme.textTheme.headlineSmall),
          const SizedBox(height: 8),
          Row(children: [
            Chip(label: Text(detail.tty)),
            const SizedBox(width: 8),
            Text('RXCUI: ${detail.rxcui}', style: theme.textTheme.bodySmall),
          ]),
          const SizedBox(height: 24),

          if (detail.ingredients.isNotEmpty) ...[
            _SectionHeader('Ingredients'),
            ...detail.ingredients.map((i) => _ConceptTile(concept: i)),
            const SizedBox(height: 16),
          ],

          if (detail.doseForms.isNotEmpty) ...[
            _SectionHeader('Dose Forms'),
            ...detail.doseForms.map((f) => _ConceptTile(concept: f)),
            const SizedBox(height: 16),
          ],

          if (detail.strengths.isNotEmpty) ...[
            _SectionHeader('Strengths'),
            Wrap(
              spacing: 8,
              children: detail.strengths.map((s) => Chip(label: Text(s))).toList(),
            ),
            const SizedBox(height: 16),
          ],

          if (detail.brands.isNotEmpty) ...[
            _SectionHeader('Brand Names'),
            ...detail.brands.map((b) => _ConceptTile(concept: b)),
            const SizedBox(height: 16),
          ],

          if (detail.generics.isNotEmpty) ...[
            _SectionHeader('Generic Ingredients'),
            ...detail.generics.map((g) => _ConceptTile(concept: g)),
            const SizedBox(height: 16),
          ],

          if (detail.ndcCodes.isNotEmpty) ...[
            _SectionHeader('NDC Codes (${detail.ndcCodes.length})'),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: detail.ndcCodes
                  .take(20)
                  .map((n) => Chip(
                        label: Text(n, style: const TextStyle(fontSize: 11)),
                        visualDensity: VisualDensity.compact,
                      ))
                  .toList(),
            ),
            if (detail.ndcCodes.length > 20)
              Text('... and ${detail.ndcCodes.length - 20} more',
                  style: theme.textTheme.bodySmall),
          ],
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(title, style: Theme.of(context).textTheme.titleMedium),
    );
  }
}

class _ConceptTile extends StatelessWidget {
  final DrugConcept concept;
  const _ConceptTile({required this.concept});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      title: Text(concept.name),
      trailing: Text(concept.tty, style: Theme.of(context).textTheme.bodySmall),
    );
  }
}
