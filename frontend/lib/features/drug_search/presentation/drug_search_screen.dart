import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../data/drug_api.dart';
import '../domain/drug_model.dart';

final drugSearchQueryProvider = StateProvider<String>((ref) => '');

final drugSearchResultsProvider = FutureProvider<DrugSearchResponse?>((ref) async {
  final query = ref.watch(drugSearchQueryProvider);
  if (query.length < 2) return null;

  final api = ref.read(drugApiProvider);
  return api.search(query);
});

class DrugSearchScreen extends ConsumerStatefulWidget {
  const DrugSearchScreen({super.key});

  @override
  ConsumerState<DrugSearchScreen> createState() => _DrugSearchScreenState();
}

class _DrugSearchScreenState extends ConsumerState<DrugSearchScreen> {
  final _controller = TextEditingController();
  Timer? _debounce;

  @override
  void dispose() {
    _controller.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  void _onSearchChanged(String query) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 400), () {
      ref.read(drugSearchQueryProvider.notifier).state = query;
    });
  }

  @override
  Widget build(BuildContext context) {
    final searchResults = ref.watch(drugSearchResultsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Drug Search')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _controller,
              onChanged: _onSearchChanged,
              decoration: const InputDecoration(
                hintText: 'Search drugs (e.g., amoxicillin, Lipitor)',
                prefixIcon: Icon(Icons.search),
              ),
              autofocus: true,
            ),
          ),
          Expanded(
            child: searchResults.when(
              data: (response) {
                if (response == null) {
                  return const Center(
                    child: Text('Type at least 2 characters to search'),
                  );
                }
                if (response.results.isEmpty) {
                  return const Center(child: Text('No drugs found'));
                }
                return ListView.builder(
                  itemCount: response.results.length,
                  itemBuilder: (context, index) {
                    final drug = response.results[index];
                    return _DrugCard(drug: drug);
                  },
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(child: Text('Error: $e')),
            ),
          ),
        ],
      ),
    );
  }
}

class _DrugCard extends StatelessWidget {
  final DrugConcept drug;

  const _DrugCard({required this.drug});

  Color _ttyColor(String tty) {
    return switch (tty) {
      'SCD' => Colors.blue,
      'SBD' => Colors.purple,
      'IN' => Colors.green,
      'BN' => Colors.orange,
      _ => Colors.grey,
    };
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: ListTile(
        title: Text(drug.name, maxLines: 2, overflow: TextOverflow.ellipsis),
        subtitle: Text('RXCUI: ${drug.rxcui}'),
        trailing: Chip(
          label: Text(drug.tty, style: const TextStyle(fontSize: 12, color: Colors.white)),
          backgroundColor: _ttyColor(drug.tty),
          padding: EdgeInsets.zero,
          visualDensity: VisualDensity.compact,
        ),
        onTap: () => context.go('/drugs/${drug.rxcui}'),
      ),
    );
  }
}
