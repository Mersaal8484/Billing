import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';

class CollectionHistoryScreen extends ConsumerWidget {
  const CollectionHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repo = ref.watch(collectionRepositoryProvider);
    final summary = repo.dailySummary();
    final receipts = repo.receipts();

    return Scaffold(
      appBar: AppBar(title: const Text('سجل تحصيلات اليوم')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                  child: _MetricCard(
                      label: 'الإجمالي',
                      value:
                          '${summary.collectedAmount.toStringAsFixed(0)} ر.س')),
              const SizedBox(width: 8),
              Expanded(
                  child: _MetricCard(
                      label: 'العمليات', value: '${summary.operationCount}')),
              const SizedBox(width: 8),
              Expanded(
                  child: _MetricCard(
                      label: 'قيد التحصيل',
                      value: '${summary.pendingAccounts}')),
            ],
          ),
          const SizedBox(height: 16),
          FilledButton.tonalIcon(
            onPressed: () {},
            icon: const Icon(Icons.sync_rounded),
            label: const Text('مزامنة / تصدير'),
          ),
          const SizedBox(height: 16),
          Text('آخر العمليات', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (receipts.isEmpty)
            const Card(
              child: ListTile(
                leading: Icon(Icons.info_outline),
                title: Text('لا توجد عمليات جديدة في هذه الجلسة'),
                subtitle: Text('تظهر هنا الإيصالات التي تسجلها أثناء التجربة.'),
              ),
            )
          else
            ...receipts.map(
              (receipt) => Card(
                child: ListTile(
                  leading: const Icon(Icons.receipt_long_outlined),
                  title: Text(receipt.reference),
                  subtitle: Text(receipt.account.customer.name),
                  trailing: Text('${receipt.amount.toStringAsFixed(0)} ر.س'),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  final String label;
  final String value;

  const _MetricCard({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Text(label, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 4),
            Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
          ],
        ),
      ),
    );
  }
}
