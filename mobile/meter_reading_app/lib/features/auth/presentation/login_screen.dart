import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../core/network/odoo_api_client.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _userCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  bool _loading = false;
  bool _obscure = true;
  String? _errorText;

  @override
  void dispose() {
    _userCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 32),
                  CircleAvatar(
                    radius: 38,
                    backgroundColor: scheme.primaryContainer,
                    child: Icon(Icons.speed_rounded,
                        size: 38, color: scheme.onPrimaryContainer),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'تطبيق الكاشف والمتحصل',
                    textAlign: TextAlign.center,
                    style: Theme.of(context)
                        .textTheme
                        .headlineSmall
                        ?.copyWith(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'المؤسسة العامة للكهرباء — الجمهورية اليمنية',
                    textAlign: TextAlign.center,
                    style: Theme.of(context)
                        .textTheme
                        .bodyMedium
                        ?.copyWith(color: scheme.outline),
                  ),
                  const SizedBox(height: 32),
                  TextFormField(
                    controller: _userCtrl,
                    decoration: const InputDecoration(
                      labelText: 'اسم المستخدم',
                      prefixIcon: Icon(Icons.person_outline),
                    ),
                    validator: (v) =>
                        (v == null || v.isEmpty) ? 'مطلوب' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _passCtrl,
                    obscureText: _obscure,
                    decoration: InputDecoration(
                      labelText: 'كلمة المرور',
                      prefixIcon: const Icon(Icons.lock_outline),
                      suffixIcon: IconButton(
                        tooltip: _obscure ? 'إظهار' : 'إخفاء',
                        icon: Icon(_obscure
                            ? Icons.visibility_off
                            : Icons.visibility),
                        onPressed: () =>
                            setState(() => _obscure = !_obscure),
                      ),
                    ),
                    validator: (v) =>
                        (v == null || v.isEmpty) ? 'مطلوب' : null,
                  ),
                  if (_errorText != null) ...[
                    const SizedBox(height: 12),
                    Text(
                      _errorText!,
                      textAlign: TextAlign.center,
                      style: Theme.of(context)
                          .textTheme
                          .bodyMedium
                          ?.copyWith(color: scheme.error),
                    ),
                  ],
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: _loading ? null : _submit,
                    child: _loading
                        ? const SizedBox(
                            height: 22,
                            width: 22,
                            child: CircularProgressIndicator(strokeWidth: 2.5))
                        : const Text('تسجيل الدخول'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _errorText = null;
    });

    try {
      final auth = ref.read(authServiceProvider);
      final userInfo = await auth.login(
        db: 'invoice_utility_erp',
        login: _userCtrl.text.trim(),
        password: _passCtrl.text,
      );

      // ✅ حفظ بيانات المستخدم والأدوار في Provider
      ref.read(currentUserProvider.notifier).state = userInfo;
      ref.read(authStateProvider.notifier).state = true;

      if (mounted) {
        // توجيه حسب الدور
        _navigateByRole(userInfo.roles ?? {});
      }
    } on OdooSessionExpiredException catch (e) {
      setState(() => _errorText = e.message);
    } on OdooApiException catch (e) {
      setState(() => _errorText = e.message);
    } catch (e) {
      setState(() => _errorText = 'تعذر الاتصال بالسيرفر — تحقق من الشبكة');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _navigateByRole(Map<String, bool> roles) {
    if (!mounted) return;

    // مشرف → لوحة المشرف
    if (roles['is_supervisor'] == true) {
      context.go('/supervisor');
      return;
    }
    // محصل فقط → شاشة التحصيل
    if (roles['is_collector'] == true &&
        roles['is_meter_reader'] != true) {
      context.go('/collector');
      return;
    }
    // كاشف أو عام → الرئيسية
    context.go('/dashboard');
  }
}
