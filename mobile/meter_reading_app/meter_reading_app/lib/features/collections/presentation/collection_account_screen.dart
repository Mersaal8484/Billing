import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../domain/collection_models.dart';

class CollectionAccountScreen extends ConsumerWidget {
  final String accountId;

  const CollectionAccountScreen({super.key, required this.accountId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return FutureBuilder<CollectionAccount?>(
      future: ref.read(collectionRepositoryProvider).findById(accountId),
      builder: (context, snapshot) {
        final account = snapshot.data;
        return Scaffold(
          appBar: AppBar(title: const Text('حساب المشترك')),
          body: snapshot.connectionState == ConnectionState.waiting
              ? const LoadingState()
              : account == null
                  ? const EmptyState(
                      icon: Icons.error_outline, title: 'الحساب غير موجود')
                  : _AccountContent(account: account),
          bottomNavigationBar: account == null
              ? null
              : SafeArea(
                  minimum: const EdgeInsets.all(16),
                  child: FilledButton.icon(
                    onPressed: () =>
                        context.push('/collector/payment/${account.id}'),
                    icon: const Icon(Icons.payments_outlined),
                    label: const Text('تسجيل تحصيل'),
                  ),
                ),
        );
      },
    );
  }
}

class _AccountContent extends StatelessWidget {
  final CollectionAccount account;

  const _AccountContent({required this.account});

  @override
  Widget build(BuildContext context) {
    final disconnected = account.meter.connectionStatus == 'disconnected';
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(account.customer.name,
                          style: Theme.of(context).textTheme.titleLarge),
                    ),
                    SyncStatusChip(
                      label: disconnected ? 'مقطوع' : 'متصل',
                      color: disconnected
                          ? Theme.of(context).colorScheme.error
                          : Theme.of(context).colorScheme.primary,
                      icon: disconnected
                          ? Icons.power_off_rounded
                          : Icons.power_rounded,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                _InfoRow(
                    label: 'رقم المشترك',
                    value: account.customer.customerNumber),
                _InfoRow(
                    label: 'رقم الحساب', value: account.customer.accountNumber),
                _InfoRow(label: 'رقم العداد', value: account.meter.meterNumber),
                _InfoRow(
                    label: 'المنطقة',
                    value:
                        '${account.customer.regionName} · ${account.customer.areaName}'),
                const Divider(height: 24),
                _InfoRow(
                    label: 'الرصيد الحالي',
                    value: '${account.balance.toStringAsFixed(0)} ﷼'),
                _InfoRow(
                    label: 'الدين المستحق',
                    value: '${account.debtAmount.toStringAsFixed(0)} ﷼'),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text('الفواتير والمستحقات',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        ...account.invoices.map((invoice) => _InvoiceTile(invoice: invoice)),
      ],
    );
  }
}

class _InvoiceTile extends StatelessWidget {
  final CollectionInvoice invoice;

  const _InvoiceTile({required this.invoice});

  @override
  Widget build(BuildContext context) {
    final color = switch (invoice.status) {
      InvoiceStatus.paid => Colors.green,
      InvoiceStatus.overdue => Colors.red,
      InvoiceStatus.unpaid => Colors.orange,
    };
    final label = switch (invoice.status) {
      InvoiceStatus.paid => 'مدفوعة',
      InvoiceStatus.overdue => 'متأخرة',
      InvoiceStatus.unpaid => 'غير مدفوعة',
    };
    return Card(
      child: ListTile(
        leading: Icon(Icons.receipt_long_outlined, color: color),
        title: Text(invoice.invoiceNumber),
        subtitle: Text('الاستحقاق: ${_date(invoice.dueDate)}'),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text('${invoice.amount.toStringAsFixed(0)} ﷼',
                style: const TextStyle(fontWeight: FontWeight.w800)),
            Text(label,
                style: TextStyle(
                    color: color, fontSize: 12, fontWeight: FontWeight.w700)),
          ],
        ),
      ),
    );
  }

  String _date(DateTime value) =>
      '${value.year}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: TextStyle(color: Theme.of(context).colorScheme.outline)),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.end,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}
