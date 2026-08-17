import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../domain/collection_models.dart';

class CollectorHomeScreen extends ConsumerStatefulWidget {
  const CollectorHomeScreen({super.key});

  @override
  ConsumerState<CollectorHomeScreen> createState() =>
      _CollectorHomeScreenState();
}

class _CollectorHomeScreenState extends ConsumerState<CollectorHomeScreen> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final accounts = ref.watch(collectionAccountsProvider(_query));
    final summary = ref.watch(collectionRepositoryProvider).dailySummary();

    return Scaffold(
      appBar: AppBar(title: const Text('المتحصل')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              onChanged: (value) => setState(() => _query = value),
              decoration: const InputDecoration(
                hintText: 'بحث يدوي برقم المشترك أو الحساب أو العداد',
                prefixIcon: Icon(Icons.search_rounded),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Expanded(
                  child: _SummaryTile(
                    icon: Icons.payments_outlined,
                    label: 'محصل اليوم',
                    value: '${summary.collectedAmount.toStringAsFixed(0)} ﷼',
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _SummaryTile(
                    icon: Icons.receipt_long_outlined,
                    label: 'العمليات',
                    value: '${summary.operationCount}',
                  ),
                ),
              ],
            ),
          ),
          Align(
            alignment: AlignmentDirectional.centerEnd,
            child: TextButton.icon(
              onPressed: () => context.push('/collector/history'),
              icon: const Icon(Icons.history_rounded),
              label: const Text('سجل التحصيل'),
            ),
          ),
          Expanded(
            child: accounts.when(
              loading: () => const LoadingState(),
              error: (e, _) =>
                  ErrorState(message: 'تعذر تحميل حسابات التحصيل: $e'),
              data: (list) {
                if (list.isEmpty) {
                  return const EmptyState(
                    icon: Icons.search_off_rounded,
                    title: 'لا توجد نتائج',
                    subtitle: 'استخدم رقم الحساب أو اسم المشترك.',
                  );
                }
                return ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  itemCount: list.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, index) =>
                      _CollectionAccountTile(account: list[index]),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _SummaryTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _SummaryTile(
      {required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Icon(icon, color: Theme.of(context).colorScheme.primary),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: Theme.of(context).textTheme.bodySmall),
                  Text(value,
                      style: const TextStyle(fontWeight: FontWeight.w800)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CollectionAccountTile extends StatelessWidget {
  final CollectionAccount account;

  const _CollectionAccountTile({required this.account});

  @override
  Widget build(BuildContext context) {
    final disconnected = account.meter.connectionStatus == 'disconnected';
    return Card(
      child: ListTile(
        onTap: () => context.push('/collector/accounts/${account.id}'),
        leading: CircleAvatar(
          backgroundColor: disconnected
              ? Theme.of(context).colorScheme.errorContainer
              : Theme.of(context).colorScheme.primaryContainer,
          child: Icon(
            disconnected
                ? Icons.power_off_rounded
                : Icons.person_outline_rounded,
            color: disconnected
                ? Theme.of(context).colorScheme.onErrorContainer
                : Theme.of(context).colorScheme.onPrimaryContainer,
          ),
        ),
        title: Text(account.customer.name,
            style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(
            '${account.customer.accountNumber} · عداد ${account.meter.meterNumber}'),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text('${account.dueTotal.toStringAsFixed(0)} ﷼',
                style: const TextStyle(fontWeight: FontWeight.w800)),
            Text(disconnected ? 'مقطوع' : 'متصل',
                style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}
