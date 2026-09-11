import \'package:flutter/material.dart\';
import \'package:flutter_riverpod/flutter_riverpod.dart\';
import \'package:go_router/go_router.dart\';

import \'../../../app/providers.dart\';
import \'../../../shared/widgets/state_widgets.dart\';
import \'../domain/collection_models.dart\';

class CollectorHomeScreen extends ConsumerStatefulWidget {
  const CollectorHomeScreen({super.key});

  @override
  ConsumerState<CollectorHomeScreen> createState() =>
      _CollectorHomeScreenState();
}

class _CollectorHomeScreenState extends ConsumerState<CollectorHomeScreen> {
  String _query = \'\';

  @override
  Widget build(BuildContext context) {
    final accounts = ref.watch(collectionAccountsProvider(_query));
    final summary = ref.watch(collectionRepositoryProvider).dailySummary();

    return Scaffold(
      appBar: AppBar(title: const Text(\'المتحصل\')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              onChanged: (value) => setState(() => _query = value),
              decoration: const InputDecoration(
                hintText: \'بحث يدوي برقم المشترك أو الحساب أو العداد\',
                prefixIcon: Icon(Icons.search_rounded),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(children: [
              Expanded(child: _SummaryTile(icon: Icons.payments_outlined, label: \'هذه الجلسة\', value: \'\ ﷼\')),
              const SizedBox(width: 8),
              Expanded(child: _SummaryTile(icon: Icons.receipt_long_outlined, label: \'العمليات\', value: \'\\')),
            ]),
          ),
          Align(
            alignment: AlignmentDirectional.centerEnd,
            child: TextButton.icon(
              onPressed: () => context.push(\'/collector/history\'),
              icon: const Icon(Icons.history_rounded),
              label: const Text(\'سجل التحصيل\'),
            ),
          ),
          Expanded(
            child: accounts.when(
              loading: () => const LoadingState(),
              error: (e, _) => ErrorState(message: \'تعذر تحميل حسابات التحصيل: \\'),
              data: (list) {
                if (list.isEmpty) {
                  return const EmptyState(icon: Icons.search_off_rounded, title: \'لا توجد نتائج\', subtitle: \'استخدم رقم الحساب أو اسم المشترك.\');
                }
                return ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  itemCount: list.length,
                  itemBuilder: (context, index) => _AccountWithInvoices(account: list[index]),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

// بطاقة المشترك + قائمة فواتيره
class _AccountWithInvoices extends StatelessWidget {
  final CollectionAccount account;
  const _AccountWithInvoices({required this.account});

  @override
  Widget build(BuildContext context) {
    final invoices = [...account.invoices]..sort((a, b) => b.dueDate.compareTo(a.dueDate));
    final paid = invoices.where((i) => i.status == InvoiceStatus.paid).length;
    final unpaid = invoices.where((i) => i.status == InvoiceStatus.unpaid || i.status == InvoiceStatus.partiallyPaid).length;
    final overdue = invoices.where((i) => i.status == InvoiceStatus.overdue).length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _CollectionAccountTile(account: account),
        const SizedBox(height: 8),
        if (invoices.isNotEmpty) ...[
          _InvoiceSummaryBar(total: invoices.length, paid: paid, unpaid: unpaid, overdue: overdue),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Text(\'فواتير المشترك\', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
          ),
          ...invoices.map((inv) => _InvoiceCard(invoice: inv)),
        ] else ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Center(child: Text(\'لا توجد فواتير لهذا المشترك\', style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.outline))),
          ),
        ],
        const SizedBox(height: 16),
        const Divider(),
      ],
    );
  }
}

class _InvoiceSummaryBar extends StatelessWidget {
  final int total, paid, unpaid, overdue;
  const _InvoiceSummaryBar({required this.total, required this.paid, required this.unpaid, required this.overdue});

  @override
  Widget build(BuildContext context) {
    final s = Theme.of(context).colorScheme;
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _SummaryChip(label: \'إجمالي\', value: \'\\', color: s.onSurfaceVariant),
            _SummaryChip(label: \'مسددة\', value: \'\\', color: Colors.green.shade700),
            _SummaryChip(label: \'غير مسددة\', value: \'\\', color: s.onSurfaceVariant),
            _SummaryChip(label: \'متأخرة\', value: \'\\', color: s.error),
          ],
        ),
      ),
    );
  }
}

class _SummaryChip extends StatelessWidget {
  final String label, value;
  final Color color;
  const _SummaryChip({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) => Column(children: [
    Text(value, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: color)),
    Text(label, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: color)),
  ]);
}

class _InvoiceCard extends StatelessWidget {
  final CollectionInvoice invoice;
  const _InvoiceCard({required this.invoice});

  @override
  Widget build(BuildContext context) {
    final s = Theme.of(context).colorScheme;
    final (badgeColor, badgeText) = switch (invoice.status) {
      InvoiceStatus.paid => (Colors.green.shade700, \'مسدد\'),
      InvoiceStatus.overdue => (s.error, \'متأخرة\'),
      InvoiceStatus.partiallyPaid => (Colors.orange.shade700, \'مدفوع جزئياً\'),
      InvoiceStatus.unpaid => (s.onSurfaceVariant, \'غير مسدد\'),
    };
    final period = \'\/ \\';
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Row(children: [
          Icon(
            invoice.status == InvoiceStatus.paid ? Icons.check_circle_outline_rounded : invoice.status == InvoiceStatus.overdue ? Icons.warning_amber_rounded : Icons.receipt_long_outlined,
            color: badgeColor, size: 22,
          ),
          const SizedBox(width: 10),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(\'فاتورة \\', style: const TextStyle(fontWeight: FontWeight.w700)),
            Text(\'رقم: \\', style: Theme.of(context).textTheme.bodySmall),
          ])),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(\'\ ﷼\', style: const TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(color: badgeColor.withOpacity(0.12), borderRadius: BorderRadius.circular(20)),
              child: Text(badgeText, style: TextStyle(color: badgeColor, fontSize: 11, fontWeight: FontWeight.w600)),
            ),
          ]),
        ]),
      ),
    );
  }
}

class _SummaryTile extends StatelessWidget {
  final IconData icon;
  final String label, value;
  const _SummaryTile({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Row(children: [
        Icon(icon, color: Theme.of(context).colorScheme.primary),
        const SizedBox(width: 8),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: Theme.of(context).textTheme.bodySmall),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
        ])),
      ]),
    ),
  );
}

class _CollectionAccountTile extends StatelessWidget {
  final CollectionAccount account;
  const _CollectionAccountTile({required this.account});

  @override
  Widget build(BuildContext context) {
    final disconnected = account.meter.connectionStatus == \'disconnected\';
    return Card(
      child: ListTile(
        onTap: () => context.push(\'/collector/accounts/\\'),
        leading: CircleAvatar(
          backgroundColor: disconnected ? Theme.of(context).colorScheme.errorContainer : Theme.of(context).colorScheme.primaryContainer,
          child: Icon(disconnected ? Icons.power_off_rounded : Icons.person_outline_rounded, color: disconnected ? Theme.of(context).colorScheme.onErrorContainer : Theme.of(context).colorScheme.onPrimaryContainer),
        ),
        title: Text(account.customer.name, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(\'\ · عداد \\'),
        trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(\'\ ﷼\', style: const TextStyle(fontWeight: FontWeight.w800)),
          Text(disconnected ? \'مقطوع\' : \'متصل\', style: Theme.of(context).textTheme.bodySmall),
        ]),
      ),
    );
  }
}
