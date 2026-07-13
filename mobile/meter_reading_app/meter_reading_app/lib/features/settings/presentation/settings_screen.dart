import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(title: const Text('الإعدادات')),
      body: ListView(
        children: [
          const _SectionHeader('الحساب'),
          const ListTile(
            leading: CircleAvatar(child: Icon(Icons.person_outline)),
            title: Text('reader01'),
            subtitle: Text('قارئ عدادات — منطقة أ'),
          ),
          const _SectionHeader('المزامنة'),
          SwitchListTile(
            value: true,
            onChanged: (_) {},
            title: const Text('مزامنة تلقائية في الخلفية'),
            subtitle: const Text(
                'يستخدم WorkManager لجدولة المزامنة عند توفر الشبكة'),
          ),
          SwitchListTile(
            value: false,
            onChanged: (_) {},
            title: const Text('المزامنة عبر بيانات الجوال'),
            subtitle: const Text(
                'افتراضياً تتم المزامنة عبر Wi-Fi فقط لتوفير الباقة'),
          ),
          const _SectionHeader('حول التطبيق'),
          const ListTile(
              title: Text('الإصدار'), trailing: Text('0.1.0 (مرحلة الواجهة)')),
          const ListTile(
            title: Text('حالة التكامل مع Odoo'),
            subtitle:
                Text('لم يتم الربط بعد — قيد استخدام بيانات محاكاة محلية'),
          ),
          const Divider(),
          Padding(
            padding: const EdgeInsets.all(16),
            child: OutlinedButton.icon(
              onPressed: () {
                ref.read(authStateProvider.notifier).state = false;
                context.go('/login');
              },
              icon: const Icon(Icons.logout_rounded),
              label: const Text('تسجيل الخروج'),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
      child: Text(title,
          style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: Theme.of(context).colorScheme.primary)),
    );
  }
}
