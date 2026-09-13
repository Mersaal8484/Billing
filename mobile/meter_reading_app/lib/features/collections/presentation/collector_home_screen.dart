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
  static const _pageSize = 50;

  final _scrollController = ScrollController();
  String _query = '';
  int _visibleLimit = _pageSize;
  bool _syncing = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) => _syncPeriodInvoices());
  }

  @override
  void dispose() {
    _scrollController
      ..removeListener(_onScroll)
      ..dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final position = _scrollController.position;
    if (position.pixels >= position.maxScrollExtent - 240) {
      setState(() => _visibleLimit += _pageSize);
    }
  }

  Future<void> _syncPeriodInvoices() async {
    if (_syncing) return;
    setState(() => _syncing = true);
    try {
      final period =
          await ref.read(collectionRepositoryProvider).syncPeriodInvoices();
      if (!mounted) return;
      final message = period == null
          ? (ref.read(collectionRepositoryProvider).periodMessage ??
              'لا توجد فترة تحصيل مفتوحة حالياً.')
          : 'تم تحديث فواتير فترة التحصيل: ${period.name}';
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('تعذر تحديث فواتير التحصيل: $error'),
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
      );
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final repository = ref.watch(collectionRepositoryProvider);
    final accounts = ref.watch(collectionAccountsProvider(_query));
    final summary = repository.dailySummary();
    final period = repository.currentPeriod;
    final periodMessage = repository.periodMessage;

    return Scaffold(
      appBar: AppBar(
        title: const Text('المتحصل'),
        actions: [
          IconButton(
            tooltip: 'تقرير التحصيل',
            onPressed: () => context.push('/collector/report'),
            icon: const Icon(Icons.analytics_outlined),
          ),
          IconButton(
            tooltip: 'مسح QR',
            onPressed: () => context.push('/collector/qr'),
            icon: const Icon(Icons.qr_code_scanner_rounded),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              textInputAction: TextInputAction.search,
              onChanged: (value) => setState(() {
                _query = value;
                _visibleLimit = _pageSize;
              }),
              decoration: const InputDecoration(
                hintText: 'بحث يدوي برقم المشترك أو الحساب أو العداد أو الاسم',
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
                    label: 'هذه الجلسة',
                    value: '${summary.collectedAmount.toStringAsFixed(0)} ريال',
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
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
            child: Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _syncing ? null : _syncPeriodInvoices,
                    icon: _syncing
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.sync_rounded),
                    label: Text(_syncing ? 'جارٍ التحديث...' : 'مزامنة الفواتير'),
                  ),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: () => context.push('/collector/history'),
                  icon: const Icon(Icons.history_rounded),
                  label: const Text('السجل'),
                ),
              ],
            ),
          ),
          if (period != null || periodMessage != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: _PeriodBanner(
                text: period != null
                    ? 'فترة التحصيل الحالية: ${period.name}'
                    : periodMessage!,
                active: period != null,
              ),
            ),
          Expanded(
            child: accounts.when(
              loading: () => const LoadingState(),
              error: (e, _) => ErrorState(
                message: 'تعذر تحميل حسابات التحصيل: $e',
                onRetry: _syncPeriodInvoices,
              ),
              data: (list) {
                if (list.isEmpty) {
                  return EmptyState(
                    icon: Icons.search_off_rounded,
                    title: period == null ? 'لا توجد فترة تحصيل مفتوحة' : 'لا توجد نتائج',
                    subtitle: period == null
                        ? 'افتح فترة تحصيل من النظام ثم اضغط مزامنة الفواتير.'
                        : 'استخدم رقم الحساب أو اسم المشترك أو اضغط مزامنة الفواتير.',
                  );
                }
                final visible = list.take(_visibleLimit).toList();
                return ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  itemCount: visible.length + (visible.length < list.length ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index >= visible.length) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 16),
                        child: Center(child: Text('مرر لأسفل لعرض المزيد')),
                      );
                    }
                    return _AccountWithInvoices(account: visible[index]);
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _PeriodBanner extends StatelessWidget {
  const _PeriodBanner({required this.text, required this.active});

  final String text;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: active ? colors.primaryContainer : colors.errorContainer,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: active ? colors.onPrimaryContainer : colors.onErrorContainer,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _AccountWithInvoices extends StatelessWidget {
  const _AccountWithInvoices({required this.account});

  final CollectionAccount account;

  @override
  Widget build(BuildContext context) {
    final invoices = [...account.invoices]
      ..sort((a, b) => b.dueDate.compareTo(a.dueDate));

    final paid = invoices.where((i) => i.status == InvoiceStatus.paid).length;
    final unpaid = invoices
        .where((i) =>
            i.status == InvoiceStatus.unpaid ||
            i.status == InvoiceStatus.partiallyPaid)
        .length;
    final overdue =
        invoices.where((i) => i.status == InvoiceStatus.overdue).length;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _CollectionAccountTile(account: account),
        const SizedBox(height: 8),
        _InvoiceSummaryBar(
          total: invoices.length,
          paid: paid,
          unpaid: unpaid,
          overdue: overdue,
        ),
        const SizedBox(height: 8),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Text(
            'فواتير المشترك',
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
        ),
        if (invoices.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Center(
              child: Text(
                'لا توجد فواتير لهذا المشترك',
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: Theme.of(context).colorScheme.outline),
              ),
            ),
          )
        else
          ...invoices.map(
            (invoice) => _InvoiceCard(account: account, invoice: invoice),
          ),
        const SizedBox(height: 16),
        const Divider(),
      ],
    );
  }
}

class _InvoiceSummaryBar extends StatelessWidget {
  const _InvoiceSummaryBar({
    required this.total,
    required this.paid,
    required this.unpaid,
    required this.overdue,
  });

  final int total;
  final int paid;
  final int unpaid;
  final int overdue;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _SummaryChip(
              label: 'إجمالي',
              value: '$total',
              color: colors.onSurfaceVariant,
            ),
            _SummaryChip(
              label: 'مسددة',
              value: '$paid',
              color: Colors.green.shade700,
            ),
            _SummaryChip(
              label: 'غير مسددة',
              value: '$unpaid',
              color: colors.onSurfaceVariant,
            ),
            _SummaryChip(label: 'متأخرة', value: '$overdue', color: colors.error),
          ],
        ),
      ),
    );
  }
}

class _SummaryChip extends StatelessWidget {
  const _SummaryChip({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) => Column(
        children: [
          Text(
            value,
            style: TextStyle(
              fontWeight: FontWeight.w800,
              fontSize: 16,
              color: color,
            ),
          ),
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: color),
          ),
        ],
      );
}

class _InvoiceCard extends StatelessWidget {
  const _InvoiceCard({required this.account, required this.invoice});

  final CollectionAccount account;
  final CollectionInvoice invoice;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final (badgeColor, badgeText) = switch (invoice.status) {
      InvoiceStatus.paid => (Colors.green.shade700, 'مسدد'),
      InvoiceStatus.partiallyPaid => (Colors.orange.shade700, 'مدفوع جزئياً'),
      InvoiceStatus.overdue => (colors.error, 'متأخرة'),
      InvoiceStatus.unpaid => (colors.outline, 'غير مسدد'),
    };

    final period =
        '${invoice.dueDate.month.toString().padLeft(2, '0')}/${invoice.dueDate.year}';
    final canCollect = invoice.amountResidual > 0;

    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Row(
          children: [
            Icon(
              invoice.status == InvoiceStatus.paid
                  ? Icons.check_circle_outline_rounded
                  : invoice.status == InvoiceStatus.overdue
                      ? Icons.warning_amber_rounded
                      : Icons.receipt_long_outlined,
              color: badgeColor,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'فاتورة $period',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  Text(
                    'رقم الفاتورة: ${invoice.invoiceNumber}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      _StatusBadge(color: badgeColor, text: badgeText),
                      Text(
                        'المتبقي: ${invoice.amountResidual.toStringAsFixed(0)} ريال',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '${invoice.amount.toStringAsFixed(0)} ريال',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 6),
                FilledButton.tonalIcon(
                  onPressed: canCollect
                      ? () => context.push(
                            '/collector/payment/${account.id}',
                            extra: invoice,
                          )
                      : null,
                  icon: const Icon(Icons.payments_outlined, size: 18),
                  label: const Text('تحصيل'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.color, required this.text});

  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _SummaryTile extends StatelessWidget {
  const _SummaryTile({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

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
                  Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
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
  const _CollectionAccountTile({required this.account});

  final CollectionAccount account;

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
            disconnected ? Icons.power_off_rounded : Icons.person_outline_rounded,
            color: disconnected
                ? Theme.of(context).colorScheme.onErrorContainer
                : Theme.of(context).colorScheme.onPrimaryContainer,
          ),
        ),
        title: Text(
          account.customer.name,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        subtitle: Text(
          '${account.customer.accountNumber} · عداد ${account.meter.meterNumber}',
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              '${account.dueTotal.toStringAsFixed(0)} ريال',
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
            Text(
              disconnected ? 'مقطوع' : 'متصل',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
