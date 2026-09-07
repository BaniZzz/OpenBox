import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/appearance/tokens.dart';
import '../../../shared/appearance/type_scale.dart';
import '../../../shared/i18n/i18n.dart';
import '../../../shared/models/billing.dart';
import '../../../shared/utils/format.dart';
import '../../../shared/widgets/toast.dart';
import '../api/billing_api.dart';
import '../payment/payment_launcher.dart';
import '../state/billing_providers.dart';
import 'billing_widgets.dart';

class BillingOrdersTab extends ConsumerStatefulWidget {
  const BillingOrdersTab({super.key});

  @override
  ConsumerState<BillingOrdersTab> createState() => _BillingOrdersTabState();
}

class _BillingOrdersTabState extends ConsumerState<BillingOrdersTab> {
  final _search = TextEditingController();
  int _page = 1;
  String? _status;
  String? _provider;
  String? _orderId;
  String? _busyOrder;
  String? _busyAction;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  BillingOrderQuery get _query => BillingOrderQuery(
    page: _page,
    status: _status,
    provider: _provider,
    orderId: _orderId,
  );

  PaymentProviderInfo? _findProvider(
    List<PaymentProviderInfo> providers,
    String id,
  ) {
    for (final provider in providers) {
      if (provider.id == id) return provider;
    }
    return null;
  }

  Future<void> _act(
    String action,
    PaymentOrder order,
    PaymentProviderInfo? provider,
  ) async {
    if (_busyOrder != null) return;
    setState(() {
      _busyOrder = order.id;
      _busyAction = action;
    });
    final i18n = ref.read(i18nProvider);
    try {
      PaymentOrder result;
      final api = ref.read(billingApiProvider);
      switch (action) {
        case 'launch':
          if (provider == null) throw StateError('Missing payment provider');
          result =
              (await ref.read(paymentLauncherProvider).launch(order, provider))
                  .order;
        case 'refresh':
          result = await api.refreshOrder(order.id);
          if (result.pending) {
            ref
                .read(toastProvider.notifier)
                .info(i18n.t('billing:usage.paymentNotConfirmed'));
          }
        case 'cancel':
          result = await api.cancelOrder(order.id);
        default:
          throw StateError('Unknown payment action');
      }
      if (result.status == 'paid') {
        ref
            .read(toastProvider.notifier)
            .success(
              i18n.t(
                'billing:usage.paid',
                vars: {'value': formatCredits(result.credits)},
              ),
            );
      }
      if (mounted) invalidateBilling(ref);
    } catch (_) {
      final key = switch (action) {
        'refresh' => 'billing:usage.queryPaymentError',
        'cancel' => 'billing:usage.cancelPaymentError',
        _ => 'billing:usage.paymentError',
      };
      ref.read(toastProvider.notifier).error(i18n.t(key));
    } finally {
      if (mounted) {
        setState(() {
          _busyOrder = null;
          _busyAction = null;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final i18n = ref.watch(i18nProvider);
    final providersAsync = ref.watch(billingProvidersProvider);
    final providers =
        providersAsync.valueOrNull ?? const <PaymentProviderInfo>[];
    final query = _query;
    final orders = ref.watch(billingOrdersProvider(query));
    final result = orders.valueOrNull;

    return I18nScope(
      state: i18n,
      child: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(billingProvidersProvider);
          ref.invalidate(billingOrdersProvider(query));
        },
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    i18n.t('billing:usage.paymentHistory'),
                    style: TextStyle(
                      fontSize: FontSizes.lg,
                      fontWeight: FontWeight.w500,
                      color: tokens.ink,
                    ),
                  ),
                ),
                Text(
                  i18n.t(
                    'billing:orders.count',
                    vars: {'count': result?.total ?? 0},
                  ),
                  style: TextStyle(fontSize: FontSizes.sm, color: tokens.n600),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _OrderFilters(
              search: _search,
              status: _status,
              provider: _provider,
              providers: providers,
              onStatus: (value) => setState(() {
                _status = value;
                _page = 1;
              }),
              onProvider: (value) => setState(() {
                _provider = value;
                _page = 1;
              }),
              onSearch: () => setState(() {
                _orderId = _search.text.trim().isEmpty
                    ? null
                    : _search.text.trim();
                _page = 1;
              }),
            ),
            if (orders.hasError || providersAsync.hasError) ...[
              const SizedBox(height: 10),
              BillingErrorBar(
                label: i18n.t('billing:usage.paymentHistoryError'),
                onRetry: () {
                  ref.invalidate(billingProvidersProvider);
                  ref.invalidate(billingOrdersProvider(query));
                },
              ),
            ],
            if (orders.isLoading && result == null) ...[
              const SizedBox(height: 28),
              Center(
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: tokens.a700,
                ),
              ),
            ],
            const SizedBox(height: 12),
            if (result?.items.isNotEmpty ?? false)
              for (final order in result!.items) ...[
                _OrderCard(
                  order: order,
                  provider: _findProvider(providers, order.provider),
                  busy: _busyOrder == order.id,
                  busyAction: _busyOrder == order.id ? _busyAction : null,
                  onLaunch: () => _act(
                    'launch',
                    order,
                    _findProvider(providers, order.provider),
                  ),
                  onRefresh: () => _act(
                    'refresh',
                    order,
                    _findProvider(providers, order.provider),
                  ),
                  onCancel: () => _act(
                    'cancel',
                    order,
                    _findProvider(providers, order.provider),
                  ),
                ),
                const SizedBox(height: 12),
              ]
            else if (!orders.isLoading && !orders.hasError)
              BillingCard(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 22),
                  child: Text(
                    i18n.t('billing:usage.noPayments'),
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: FontSizes.sm,
                      color: tokens.n600,
                    ),
                  ),
                ),
              ),
            const SizedBox(height: 6),
            BillingPager(
              page: _page,
              pages: result?.totalPages ?? 1,
              busy: orders.isLoading,
              onPrevious: () => setState(() => _page--),
              onNext: () => setState(() => _page++),
            ),
          ],
        ),
      ),
    );
  }
}

class _OrderFilters extends StatelessWidget {
  const _OrderFilters({
    required this.search,
    required this.status,
    required this.provider,
    required this.providers,
    required this.onStatus,
    required this.onProvider,
    required this.onSearch,
  });

  final TextEditingController search;
  final String? status;
  final String? provider;
  final List<PaymentProviderInfo> providers;
  final ValueChanged<String?> onStatus;
  final ValueChanged<String?> onProvider;
  final VoidCallback onSearch;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final i18n = I18nScope.of(context);
    return BillingCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            i18n.t('billing:orders.filters'),
            style: TextStyle(
              fontSize: FontSizes.sm,
              fontWeight: FontWeight.w500,
              color: tokens.ink,
            ),
          ),
          const SizedBox(height: 11),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String?>(
                  initialValue: status,
                  decoration: InputDecoration(
                    labelText: i18n.t('billing:orders.status'),
                  ),
                  items: [
                    DropdownMenuItem(
                      value: null,
                      child: Text(i18n.t('billing:orders.all')),
                    ),
                    for (final value in ['pending', 'paid', 'cancelled'])
                      DropdownMenuItem(
                        value: value,
                        child: Text(
                          i18n.t('billing:usage.paymentState.$value'),
                        ),
                      ),
                  ],
                  onChanged: onStatus,
                ),
              ),
              const SizedBox(width: 9),
              Expanded(
                child: DropdownButtonFormField<String?>(
                  initialValue: provider,
                  decoration: InputDecoration(
                    labelText: i18n.t('billing:usage.paymentChannel'),
                  ),
                  items: [
                    DropdownMenuItem(
                      value: null,
                      child: Text(i18n.t('billing:orders.allChannels')),
                    ),
                    for (final item in providers)
                      DropdownMenuItem(value: item.id, child: Text(item.name)),
                  ],
                  onChanged: onProvider,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          TextField(
            controller: search,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => onSearch(),
            decoration: InputDecoration(
              labelText: i18n.t('billing:orders.orderId'),
              hintText: i18n.t('billing:orders.orderIdPlaceholder'),
              suffixIcon: IconButton(
                onPressed: onSearch,
                icon: const Icon(Icons.search, size: 18),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _OrderCard extends StatelessWidget {
  const _OrderCard({
    required this.order,
    required this.provider,
    required this.busy,
    required this.busyAction,
    required this.onLaunch,
    required this.onRefresh,
    required this.onCancel,
  });

  final PaymentOrder order;
  final PaymentProviderInfo? provider;
  final bool busy;
  final String? busyAction;
  final VoidCallback onLaunch;
  final VoidCallback onRefresh;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final i18n = I18nScope.of(context);
    final title = order.kind == 'subscription'
        ? i18n.t(
            'billing:plans.orderTitle',
            vars: {
              'name': i18n.t('billing:plans.names.${order.planId ?? 'free'}'),
              'cycle': i18n.t(
                'billing:plans.cycles.${order.cycle ?? 'monthly'}',
              ),
            },
          )
        : i18n.t('billing:plans.extraCredits');
    return BillingCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        fontSize: FontSizes.base,
                        fontWeight: FontWeight.w500,
                        color: tokens.ink,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      i18n.t(
                        order.kind == 'subscription'
                            ? 'billing:plans.allowance.monthly'
                            : 'billing:usage.points',
                        vars: {
                          'credits': formatCredits(order.credits),
                          'value': formatCredits(order.credits),
                        },
                      ),
                      style: TextStyle(
                        fontSize: FontSizes.sm,
                        color: tokens.n600,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 11,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: tokens.n200,
                  borderRadius: BorderRadius.circular(Radii.full),
                ),
                child: Text(
                  i18n.t('billing:usage.paymentState.${order.status}'),
                  style: TextStyle(fontSize: FontSizes.sm, color: tokens.ink),
                ),
              ),
            ],
          ),
          const SizedBox(height: 15),
          Row(
            children: [
              Expanded(
                child: Text(
                  '¥${formatFen(order.amountFen)}',
                  style: TextStyle(
                    fontSize: FontSizes.xl,
                    fontWeight: FontWeight.w500,
                    color: tokens.ink,
                  ),
                ),
              ),
              Text(
                provider?.name ?? order.provider,
                style: TextStyle(fontSize: FontSizes.sm, color: tokens.n600),
              ),
            ],
          ),
          const SizedBox(height: 13),
          Text(
            i18n.t('billing:usage.orderNumber', vars: {'id': order.id}),
            style: TextStyle(fontSize: FontSizes.xs, color: tokens.n600),
          ),
          const SizedBox(height: 4),
          Text(
            '${i18n.t('billing:orders.createdAt')} '
            '${formatDateTime(order.createdAt, i18n.language)}',
            style: TextStyle(fontSize: FontSizes.xs, color: tokens.n600),
          ),
          if (order.paidAt != null) ...[
            const SizedBox(height: 4),
            Text(
              '${i18n.t('billing:orders.paidAt')} '
              '${formatDateTime(order.paidAt!, i18n.language)}',
              style: TextStyle(fontSize: FontSizes.xs, color: tokens.n600),
            ),
          ],
          if (order.cancelledAt != null) ...[
            const SizedBox(height: 4),
            Text(
              '${i18n.t('billing:orders.cancelledAt')} '
              '${formatDateTime(order.cancelledAt!, i18n.language)}',
              style: TextStyle(fontSize: FontSizes.xs, color: tokens.n600),
            ),
          ],
          if (order.reconcileRequired) ...[
            const SizedBox(height: 10),
            Text(
              i18n.t('billing:orders.closeOldCashier'),
              style: TextStyle(fontSize: FontSizes.sm, color: tokens.n600),
            ),
          ],
          if (order.pending) ...[
            const SizedBox(height: 15),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton.icon(
                  onPressed: busy ? null : onLaunch,
                  style: billingPrimaryButton(tokens),
                  icon: const Icon(Icons.open_in_new, size: 16),
                  label: Text(
                    i18n.t(
                      busy && busyAction == 'launch'
                          ? 'billing:usage.creatingOrder'
                          : 'billing:usage.resumePayment',
                    ),
                  ),
                ),
                if (provider?.supportsStatusQuery ?? false)
                  OutlinedButton.icon(
                    onPressed: busy ? null : onRefresh,
                    style: billingSecondaryButton(tokens),
                    icon: const Icon(Icons.refresh, size: 16),
                    label: Text(
                      i18n.t(
                        busy && busyAction == 'refresh'
                            ? 'billing:usage.queryingPayment'
                            : 'billing:usage.queryPayment',
                      ),
                    ),
                  ),
                if (provider?.supportsCancel ?? false)
                  OutlinedButton.icon(
                    onPressed: busy ? null : onCancel,
                    style: billingSecondaryButton(tokens),
                    icon: const Icon(Icons.close, size: 16),
                    label: Text(
                      i18n.t(
                        busy && busyAction == 'cancel'
                            ? 'billing:usage.cancellingPayment'
                            : 'billing:usage.cancelPayment',
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
