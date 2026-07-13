import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../domain/collection_models.dart';

class ReceiptScreen extends StatelessWidget {
  final CollectionReceipt receipt;

  const ReceiptScreen({super.key, required this.receipt});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('إيصال التحصيل')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Icon(Icons.verified_rounded,
                      size: 56, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(height: 12),
                  Text('تم تسجيل التحصيل',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 20),
                  _InfoRow(label: 'المرجع', value: receipt.reference),
                  _InfoRow(
                      label: 'المشترك', value: receipt.account.customer.name),
                  _InfoRow(
                      label: 'رقم الحساب',
                      value: receipt.account.customer.accountNumber),
                  _InfoRow(
                      label: 'رقم العداد',
                      value: receipt.account.meter.meterNumber),
                  _InfoRow(
                      label: 'المبلغ',
                      value: '${receipt.amount.toStringAsFixed(0)} ر.س'),
                  _InfoRow(
                      label: 'طريقة الدفع',
                      value: _methodLabel(receipt.method)),
                  _InfoRow(label: 'التاريخ', value: _dateTime(receipt.paidAt)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () {},
                  icon: const Icon(Icons.print_outlined),
                  label: const Text('طباعة'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () {},
                  icon: const Icon(Icons.sms_outlined),
                  label: const Text('إرسال'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: () => context.go('/collector'),
            icon: const Icon(Icons.home_outlined),
            label: const Text('العودة للرئيسية'),
          ),
        ],
      ),
    );
  }

  String _methodLabel(PaymentMethod method) => switch (method) {
        PaymentMethod.cash => 'نقدي',
        PaymentMethod.card => 'شبكة',
        PaymentMethod.wallet => 'محفظة',
        PaymentMethod.transfer => 'تحويل',
      };

  String _dateTime(DateTime value) =>
      '${value.year}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')} '
      '${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: TextStyle(color: Theme.of(context).colorScheme.outline)),
          Flexible(
            child: Text(value,
                textAlign: TextAlign.end,
                style: const TextStyle(fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
  }
}
