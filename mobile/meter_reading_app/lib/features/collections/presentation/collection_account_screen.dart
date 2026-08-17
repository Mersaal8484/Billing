import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../core/network/odoo_api_client.dart';
import '../domain/collection_models.dart';
import '../../../shared/widgets/state_widgets.dart';

/// شاشة تفاصيل الحساب — تجلب بيانات حية من Odoo عند الفتح
/// مثل Elecollect: Biller_Bill_Inquiry
class CollectionAccountScreen extends ConsumerStatefulWidget {
  final String accountId;
  const CollectionAccountScreen({super.key, required this.accountId});

  @override
  ConsumerState<CollectionAccountScreen> createState() =>
      _CollectionAccountScreenState();
}

class _CollectionAccountScreenState
    extends ConsumerState<CollectionAccountScreen> {
  CollectionAccount? _account;
  _LiveBillData? _liveBill;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadAccountWithLiveData();
  }

  // ── جلب البيانات الحية من Odoo ────────────────────────────────────────────

  Future<void> _loadAccountWithLiveData() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      // 1. جلب الحساب من المستودع المحلي
      final account = await ref
          .read(collectionRepositoryProvider)
          .findById(widget.accountId);

      if (account == null) {
        setState(() {
          _error = 'الحساب غير موجود';
          _loading = false;
        });
        return;
      }

      // 2. استعلام حي من Odoo عن رصيد الفترة الحالية
      _LiveBillData liveBill;
      try {
        liveBill = await _fetchLiveBillFromOdoo(account.customer.remoteId);
      } catch (_) {
        // وضع غير متصل — نعمل بالبيانات المحلية
        liveBill = _LiveBillData.fromAccount(account);
      }

      setState(() {
        _account = account;
        _liveBill = liveBill;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'خطأ في تحميل البيانات: $e';
        _loading = false;
      });
    }
  }

  Future<_LiveBillData> _fetchLiveBillFromOdoo(int customerId) async {
    final billing = ref.read(billingApiServiceProvider);

    // جلب الرصيد الإجمالي
    final balanceResult = await billing.getBillInquiry(customerId);

    // جلب قائمة الفواتير
    final billsResult = await billing.getBills(customerId);
    final billsList =
        (billsResult['bills'] as List?)?.cast<Map<String, dynamic>>() ?? [];

    return _LiveBillData(
      dueAmount: (balanceResult['due_amount'] as num?)?.toDouble() ?? 0,
      currentBill: (balanceResult['current_bill'] as num?)?.toDouble() ?? 0,
      debtAmount: (balanceResult['debt_amount'] as num?)?.toDouble() ?? 0,
      allowPartial: balanceResult['allow_partial'] != false,
      message: (balanceResult['message'] as String?) ?? '',
      lastReadingValue:
          (balanceResult['last_reading_value'] as num?)?.toDouble() ?? 0,
      bills: billsList
          .map((b) => CollectionInvoice(
                id: b['id'].toString(),
                invoiceNumber: b['name'] as String? ?? '—',
                dueDate: DateTime.tryParse(b['date_due'] as String? ?? '') ??
                    DateTime.now(),
                amount: (b['amount_total'] as num?)?.toDouble() ?? 0,
                amountResidual:
                    (b['amount_residual'] as num?)?.toDouble() ?? 0,
                status: (b['payment_state'] == 'paid')
                    ? InvoiceStatus.paid
                    : (b['overdue'] == true
                        ? InvoiceStatus.overdue
                        : InvoiceStatus.unpaid),
              ))
          .toList(),
      isOffline: false,
    );
  }

  // ── UI ────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('تفاصيل الحساب'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadAccountWithLiveData,
            tooltip: 'تحديث من Odoo',
          ),
        ],
      ),
      body: _loading
          ? const LoadingState()
          : _error != null
              ? ErrorState(
                  message: _error!,
                  onRetry: _loadAccountWithLiveData,
                )
              : _buildContent(),
    );
  }

  Widget _buildContent() {
    final account = _account!;
    final live = _liveBill!;
    final scheme = Theme.of(context).colorScheme;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // ── بطاقة المشترك ─────────────────────────────────────────────────
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    CircleAvatar(
                      backgroundColor: scheme.primaryContainer,
                      child: Icon(Icons.person_outline,
                          color: scheme.onPrimaryContainer),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(account.customer.name,
                              style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 16)),
                          Text(
                            '${account.customer.accountNumber} · عداد ${account.meter.meterNumber}',
                            style: TextStyle(color: scheme.outline),
                          ),
                        ],
                      ),
                    ),
                    if (live.isOffline)
                      Tooltip(
                        message: 'بيانات محلية',
                        child: Icon(Icons.cloud_off,
                            color: scheme.outline, size: 18),
                      ),
                  ],
                ),
                if (live.lastReadingValue > 0) ...[
                  const Divider(height: 24),
                  Row(
                    children: [
                      Icon(Icons.speed_outlined,
                          size: 16, color: scheme.outline),
                      const SizedBox(width: 6),
                      Text(
                          'آخر قراءة: ${live.lastReadingValue.toStringAsFixed(0)} kWh',
                          style: TextStyle(color: scheme.outline)),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),

        // ── بطاقة الرصيد الحي ─────────────────────────────────────────────
        Card(
          color: live.dueAmount > 0
              ? scheme.errorContainer.withOpacity(0.3)
              : scheme.primaryContainer.withOpacity(0.3),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _BalanceTile(
                      label: 'فاتورة الفترة',
                      value: live.currentBill,
                      icon: Icons.receipt_outlined,
                    ),
                    _BalanceTile(
                      label: 'المتأخرات',
                      value: live.debtAmount,
                      icon: Icons.warning_amber_outlined,
                      color: live.debtAmount > 0 ? scheme.error : null,
                    ),
                    _BalanceTile(
                      label: 'الإجمالي',
                      value: live.dueAmount,
                      icon: Icons.payments_outlined,
                      isBold: true,
                    ),
                  ],
                ),
                if (live.message.isNotEmpty) ...[
                  const Divider(height: 20),
                  Text(
                    live.message,
                    style: TextStyle(
                        fontSize: 12, color: scheme.onSurfaceVariant),
                    textAlign: TextAlign.center,
                  ),
                ],
                if (!live.allowPartial) ...[
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: scheme.errorContainer,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.block, size: 14, color: scheme.error),
                        const SizedBox(width: 6),
                        Text(
                          'الدفع الجزئي غير مسموح',
                          style: TextStyle(
                              fontSize: 12,
                              color: scheme.error,
                              fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),

        // ── قائمة الفواتير ────────────────────────────────────────────────
        if (live.bills.isNotEmpty) ...[
          Text('الفواتير',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ...live.bills.map((invoice) => _InvoiceTile(invoice: invoice)),
          const SizedBox(height: 12),
        ],

        // ── زر التحصيل ───────────────────────────────────────────────────
        FilledButton.icon(
          onPressed: live.dueAmount <= 0
              ? null
              : () => context.push(
                    '/collector/payment/${account.id}',
                    extra: live,
                  ),
          icon: const Icon(Icons.payments_outlined),
          label: Text(
            live.dueAmount > 0
                ? 'تحصيل ${live.dueAmount.toStringAsFixed(0)} ﷼'
                : 'لا يوجد مستحقات',
          ),
          style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(52)),
        ),
        const SizedBox(height: 32),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Widgets مساعدة
// ─────────────────────────────────────────────────────────────────────────────

class _BalanceTile extends StatelessWidget {
  final String label;
  final double value;
  final IconData icon;
  final bool isBold;
  final Color? color;

  const _BalanceTile({
    required this.label,
    required this.value,
    required this.icon,
    this.isBold = false,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icon, size: 20, color: color),
        const SizedBox(height: 4),
        Text(
          '${value.toStringAsFixed(0)} ﷼',
          style: TextStyle(
            fontWeight: isBold ? FontWeight.w800 : FontWeight.w600,
            fontSize: isBold ? 16 : 14,
            color: color,
          ),
        ),
        Text(label,
            style: TextStyle(
                fontSize: 11,
                color: Theme.of(context).colorScheme.outline)),
      ],
    );
  }
}

class _InvoiceTile extends StatelessWidget {
  final CollectionInvoice invoice;
  const _InvoiceTile({required this.invoice});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final color = switch (invoice.status) {
      InvoiceStatus.paid => Colors.green,
      InvoiceStatus.overdue => scheme.error,
      InvoiceStatus.unpaid => scheme.primary,
    };
    final label = switch (invoice.status) {
      InvoiceStatus.paid => 'مدفوعة',
      InvoiceStatus.overdue => 'متأخرة',
      InvoiceStatus.unpaid => 'مستحقة',
    };

    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      child: ListTile(
        dense: true,
        leading: Icon(Icons.receipt_long_outlined, color: color),
        title: Text(invoice.invoiceNumber),
        subtitle: Text(
            'تاريخ: ${invoice.dueDate.toLocal().toString().substring(0, 10)}'),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text('${invoice.amount.toStringAsFixed(0)} ﷼',
                style: const TextStyle(fontWeight: FontWeight.bold)),
            Text(label,
                style: TextStyle(fontSize: 11, color: color)),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// بيانات الفاتورة الحية من Odoo
// ─────────────────────────────────────────────────────────────────────────────

class _LiveBillData {
  final double dueAmount;
  final double currentBill;
  final double debtAmount;
  final bool allowPartial;
  final String message;
  final double lastReadingValue;
  final List<CollectionInvoice> bills;
  final bool isOffline;

  const _LiveBillData({
    required this.dueAmount,
    this.currentBill = 0,
    this.debtAmount = 0,
    this.allowPartial = true,
    this.message = '',
    this.lastReadingValue = 0,
    required this.bills,
    this.isOffline = false,
  });

  factory _LiveBillData.fromAccount(CollectionAccount account) =>
      _LiveBillData(
        dueAmount: account.dueTotal,
        currentBill: account.currentBill,
        debtAmount: account.debtAmount,
        allowPartial: account.allowPartial,
        message: account.message,
        bills: account.invoices,
        isOffline: true,
      );
}
