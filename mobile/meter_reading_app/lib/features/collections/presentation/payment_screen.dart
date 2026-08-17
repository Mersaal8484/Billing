import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../../app/providers.dart';
import '../../../core/network/odoo_api_client.dart';
import '../domain/collection_models.dart';
import '../../../shared/widgets/state_widgets.dart';

/// شاشة التحصيل — تتحقق من قواعد Odoo قبل الإرسال
/// - تحقق من Allow_Part (دفع جزئي مسموح؟)
/// - حد أدنى 500 ريال
/// - ترسل transaction_id فريد لكل عملية
/// - عند النجاح تفتح شاشة السند
class PaymentScreen extends ConsumerStatefulWidget {
  final String accountId;
  const PaymentScreen({super.key, required this.accountId});

  @override
  ConsumerState<PaymentScreen> createState() => _PaymentScreenState();
}

class _PaymentScreenState extends ConsumerState<PaymentScreen> {
  final _formKey = GlobalKey<FormState>();
  final _amountCtrl = TextEditingController();
  PaymentMethod _method = PaymentMethod.cash;
  bool _saving = false;
  bool _loading = true;
  String? _error;

  CollectionAccount? _account;
  double _dueAmount = 0;
  double _currentBill = 0;
  bool _allowPartial = true;
  String _odooMessage = '';
  bool _isOffline = false;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  @override
  void dispose() {
    _amountCtrl.dispose();
    super.dispose();
  }

  // ── تحميل البيانات الحية من Odoo ─────────────────────────────────────────

  Future<void> _loadData() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
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

      // استعلام حي من Odoo
      double due = account.dueTotal;
      double current = account.currentBill;
      bool partial = account.allowPartial;
      String msg = account.message;
      bool offline = false;

      try {
        final billing = ref.read(billingApiServiceProvider);
        final result = await billing.getBillInquiry(account.customer.remoteId);
        due = (result['due_amount'] as num?)?.toDouble() ?? due;
        current = (result['current_bill'] as num?)?.toDouble() ?? current;
        partial = result['allow_partial'] != false;
        msg = (result['message'] as String?) ?? msg;
      } catch (_) {
        offline = true;
      }

      setState(() {
        _account = account;
        _dueAmount = due;
        _currentBill = current;
        _allowPartial = partial;
        _odooMessage = msg;
        _isOffline = offline;
        _amountCtrl.text = due.toStringAsFixed(0);
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'خطأ: $e';
        _loading = false;
      });
    }
  }

  // ── تنفيذ التحصيل ─────────────────────────────────────────────────────────

  Future<void> _collect() async {
    if (!_formKey.currentState!.validate()) return;

    final account = _account!;
    final amount = double.parse(_amountCtrl.text.trim());

    // قاعدة Odoo: إذا لا يُسمح بالدفع الجزئي → يجب دفع المبلغ كاملاً
    if (!_allowPartial && amount < _currentBill && _currentBill > 0) {
      _showSnack(
        'الدفع الجزئي غير مسموح — يجب دفع ${_currentBill.toStringAsFixed(0)} ﷼ كاملاً',
        isError: true,
      );
      return;
    }

    setState(() => _saving = true);

    try {
      final billing = ref.read(billingApiServiceProvider);
      final transactionId = const Uuid().v4();

      Map<String, dynamic> result;
      String reference = transactionId;
      String displayName = '';

      if (!_isOffline) {
        // إرسال لـ Odoo
        result = await billing.pay(
          customerId: account.customer.remoteId,
          amount: amount,
          dueAmount: _dueAmount,
          paymentMethod: _methodCode(_method),
          transactionId: transactionId,
        );

        // مثل Elecollect: Error_Code == '000' → نجح
        final success = result['success'] == true ||
            result['error_code'] == '000' ||
            result['id'] != null;

        if (!success) {
          final errMsg = result['message'] as String? ??
              result['error'] as String? ??
              'فشل التحصيل';
          _showSnack(errMsg, isError: true);
          setState(() => _saving = false);
          return;
        }

        // رقم السند من Odoo — مثل display_name في Elecollect
        reference = result['display_name'] as String? ??
            result['name'] as String? ??
            result['reference'] as String? ??
            transactionId;
        displayName = reference;
      }

      // بناء السند
      final receipt = CollectionReceipt(
        reference: reference,
        displayName: displayName,
        account: account,
        amount: amount,
        method: _method,
        paidAt: DateTime.now(),
      );

      // تحديث المستودع المحلي
      await ref.read(collectionRepositoryProvider).collect(
            accountId: account.id,
            amount: amount,
            method: _method,
          );

      if (mounted) {
        context.go('/collector/receipt/${account.id}', extra: receipt);
      }
    } on OdooSessionExpiredException {
      _showSnack('انتهت الجلسة — سجّل الدخول مجدداً', isError: true);
    } on OdooApiException catch (e) {
      _showSnack(e.message, isError: true);
    } catch (e) {
      _showSnack('خطأ غير متوقع: $e', isError: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  // ── UI ────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('تحصيل دفعة'),
        centerTitle: true,
      ),
      body: _loading
          ? const LoadingState()
          : _error != null
              ? ErrorState(message: _error!, onRetry: _loadData)
              : _buildForm(),
    );
  }

  Widget _buildForm() {
    final account = _account!;
    final scheme = Theme.of(context).colorScheme;

    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // بطاقة المشترك
          Card(
            child: ListTile(
              leading: const Icon(Icons.person_outline_rounded),
              title: Text(account.customer.name,
                  style: const TextStyle(fontWeight: FontWeight.bold)),
              subtitle:
                  Text('${account.customer.accountNumber} · عداد ${account.meter.meterNumber}'),
              trailing: _isOffline
                  ? Icon(Icons.cloud_off, color: scheme.outline, size: 18)
                  : null,
            ),
          ),
          const SizedBox(height: 12),

          // ملخص المستحقات
          Card(
            color: scheme.secondaryContainer.withOpacity(0.3),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      _AmountRow(
                          label: 'فاتورة الفترة',
                          value: _currentBill),
                      _AmountRow(
                          label: 'الإجمالي المستحق',
                          value: _dueAmount,
                          isBold: true),
                    ],
                  ),
                  if (_odooMessage.isNotEmpty) ...[
                    const Divider(height: 16),
                    Text(
                      _odooMessage,
                      style: TextStyle(
                          fontSize: 12, color: scheme.onSurfaceVariant),
                      textAlign: TextAlign.center,
                    ),
                  ],
                  if (!_allowPartial) ...[
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
          const SizedBox(height: 16),

          // حقل المبلغ
          TextFormField(
            controller: _amountCtrl,
            keyboardType:
                const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))
            ],
            style: const TextStyle(
                fontSize: 28, fontWeight: FontWeight.w800),
            decoration: InputDecoration(
              labelText: 'المبلغ المحصّل',
              suffixText: '﷼',
              border: const OutlineInputBorder(),
              filled: true,
              fillColor: scheme.surfaceVariant.withOpacity(0.3),
            ),
            validator: (v) {
              if (v == null || v.isEmpty) return 'أدخل مبلغاً';
              final amount = double.tryParse(v);
              if (amount == null || amount <= 0) return 'مبلغ غير صحيح';
              if (amount < 500) return 'الحد الأدنى للتحصيل 500 ﷼';
              if (amount > 100000000) return 'المبلغ يتجاوز الحد الأقصى';
              if (!_allowPartial &&
                  _currentBill > 0 &&
                  amount < _currentBill) {
                return 'يجب دفع ${_currentBill.toStringAsFixed(0)} ﷼ كاملاً';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),

          // طريقة الدفع
          Text('طريقة الدفع',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: PaymentMethod.values
                .map((method) => ChoiceChip(
                      selected: _method == method,
                      label: Text(_methodLabel(method)),
                      avatar: Icon(_methodIcon(method), size: 18),
                      onSelected: (_) =>
                          setState(() => _method = method),
                    ))
                .toList(),
          ),
          const SizedBox(height: 24),

          // زر التحصيل
          FilledButton.icon(
            onPressed: _saving ? null : _collect,
            icon: _saving
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.check_circle_outline),
            label: Text(_saving ? 'جاري الإرسال...' : 'تأكيد التحصيل'),
            style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(52)),
          ),

          if (_isOffline)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.cloud_off, size: 14, color: scheme.outline),
                  const SizedBox(width: 4),
                  Text('وضع غير متصل — يُرسل عند توفر الشبكة',
                      style: TextStyle(
                          fontSize: 11, color: scheme.outline)),
                ],
              ),
            ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor:
          isError ? Theme.of(context).colorScheme.error : null,
    ));
  }

  String _methodCode(PaymentMethod m) => switch (m) {
        PaymentMethod.cash => 'cash',
        PaymentMethod.card => 'card',
        PaymentMethod.wallet => 'wallet',
        PaymentMethod.transfer => 'transfer',
      };

  String _methodLabel(PaymentMethod m) => switch (m) {
        PaymentMethod.cash => 'نقدي',
        PaymentMethod.card => 'شبكة',
        PaymentMethod.wallet => 'محفظة',
        PaymentMethod.transfer => 'تحويل',
      };

  IconData _methodIcon(PaymentMethod m) => switch (m) {
        PaymentMethod.cash => Icons.payments_outlined,
        PaymentMethod.card => Icons.credit_card_rounded,
        PaymentMethod.wallet => Icons.account_balance_wallet_outlined,
        PaymentMethod.transfer => Icons.account_balance_outlined,
      };
}

// ── Widget مساعد ─────────────────────────────────────────────────────────────

class _AmountRow extends StatelessWidget {
  final String label;
  final double value;
  final bool isBold;

  const _AmountRow(
      {required this.label, required this.value, this.isBold = false});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(label,
            style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.outline)),
        Text(
          '${value.toStringAsFixed(0)} ﷼',
          style: TextStyle(
            fontWeight: isBold ? FontWeight.w800 : FontWeight.w600,
            fontSize: isBold ? 18 : 14,
          ),
        ),
      ],
    );
  }
}
