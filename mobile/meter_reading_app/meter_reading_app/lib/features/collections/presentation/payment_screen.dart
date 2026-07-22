import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../shared/widgets/state_widgets.dart';
import '../domain/collection_models.dart';

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
  final Set<String> _selectedInvoiceIds = {};
  bool _initialized = false;

  @override
  void dispose() {
    _amountCtrl.dispose();
    super.dispose();
  }

  void _initInvoicesIfNeeded(CollectionAccount account) {
    if (_initialized) return;
    final unpaidInvoices = account.invoices
        .where((invoice) => invoice.status != InvoiceStatus.paid)
        .toList();
    _selectedInvoiceIds.addAll(unpaidInvoices.map((inv) => inv.id));
    if (_amountCtrl.text.isEmpty) {
      final initialTotal = unpaidInvoices.fold<double>(
          0, (sum, invoice) => sum + invoice.amount);
      _amountCtrl.text = initialTotal.toStringAsFixed(0);
    }
    _initialized = true;
  }

  void _toggleInvoice(
      CollectionAccount account, String invoiceId, bool isSelected) {
    setState(() {
      if (isSelected) {
        _selectedInvoiceIds.add(invoiceId);
      } else {
        _selectedInvoiceIds.remove(invoiceId);
      }
      final newTotal = account.invoices
          .where((inv) => _selectedInvoiceIds.contains(inv.id))
          .fold<double>(0, (sum, inv) => sum + inv.amount);
      _amountCtrl.text = newTotal.toStringAsFixed(0);
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<CollectionAccount?>(
      future: ref.read(collectionRepositoryProvider).findById(widget.accountId),
      builder: (context, snapshot) {
        final account = snapshot.data;
        return Scaffold(
          appBar: AppBar(title: const Text('تحصيل دفعة')),
          body: snapshot.connectionState == ConnectionState.waiting
              ? const LoadingState()
              : account == null
                  ? const EmptyState(
                      icon: Icons.error_outline, title: 'الحساب غير موجود')
                  : _buildForm(context, account),
        );
      },
    );
  }

  Widget _buildForm(BuildContext context, CollectionAccount account) {
    _initInvoicesIfNeeded(account);

    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.person_outline_rounded),
              title: Text(account.customer.name),
              subtitle: Text(
                  '${account.customer.accountNumber} · المستحق ${account.dueTotal.toStringAsFixed(0)} ﷼'),
            ),
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _amountCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))
            ],
            style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800),
            decoration: const InputDecoration(labelText: 'المبلغ المحصل'),
            validator: (value) {
              if (_selectedInvoiceIds.isEmpty) {
                return 'يرجى اختيار فاتورة واحدة على الأقل';
              }
              final amount = double.tryParse(value ?? '');
              if (amount == null || amount <= 0) return 'أدخل مبلغًا صحيحًا';
              return null;
            },
          ),
          const SizedBox(height: 16),
          Text('طريقة الدفع', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: PaymentMethod.values
                .map(
                  (method) => ChoiceChip(
                    selected: _method == method,
                    label: Text(_methodLabel(method)),
                    avatar: Icon(_methodIcon(method), size: 18),
                    onSelected: (_) => setState(() => _method = method),
                  ),
                )
                .toList(),
          ),
          const SizedBox(height: 16),
          Text('الفواتير المختارة',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ...account.invoices
              .where((invoice) => invoice.status != InvoiceStatus.paid)
              .map(
                (invoice) {
                  final isSelected = _selectedInvoiceIds.contains(invoice.id);
                  return CheckboxListTile(
                    value: isSelected,
                    onChanged: (checked) {
                      _toggleInvoice(account, invoice.id, checked ?? false);
                    },
                    title: Text(invoice.invoiceNumber),
                    subtitle: Text('${invoice.amount.toStringAsFixed(0)} ﷼'),
                    controlAffinity: ListTileControlAffinity.leading,
                  );
                },
              ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _saving ? null : () => _collect(account),
            icon: _saving
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.check_circle_outline),
            label: const Text('تأكيد التحصيل'),
          ),
        ],
      ),
    );
  }

  Future<void> _collect(CollectionAccount account) async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    final receipt = await ref.read(collectionRepositoryProvider).collect(
          accountId: account.id,
          amount: double.parse(_amountCtrl.text),
          method: _method,
        );
    if (!mounted) return;
    setState(() => _saving = false);
    context.go(
      '/collector/receipt/${account.id}',
      extra: receipt,
    );
  }

  String _methodLabel(PaymentMethod method) => switch (method) {
        PaymentMethod.cash => 'نقدي',
        PaymentMethod.card => 'شبكة',
        PaymentMethod.wallet => 'محفظة',
        PaymentMethod.transfer => 'تحويل',
      };

  IconData _methodIcon(PaymentMethod method) => switch (method) {
        PaymentMethod.cash => Icons.payments_outlined,
        PaymentMethod.card => Icons.credit_card_rounded,
        PaymentMethod.wallet => Icons.account_balance_wallet_outlined,
        PaymentMethod.transfer => Icons.account_balance_outlined,
      };
}
