import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/api/providers.dart';
import '../../../shared/models/billing.dart';

class BillingApi {
  BillingApi(this._dio);

  final Dio _dio;

  Future<CreditBalance> getBalance() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/billing/balance',
    );
    return CreditBalance.fromJson(response.data ?? const {});
  }

  Future<BillingPlans> getPlans() async {
    final response = await _dio.get<Map<String, dynamic>>('/api/billing/plans');
    return BillingPlans.fromJson(response.data ?? const {});
  }

  Future<BillingSubscription> getSubscription() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/billing/subscription',
    );
    return BillingSubscription.fromJson(response.data ?? const {});
  }

  Future<BillingSummary> getSummary({
    DateTime? dateFrom,
    DateTime? dateTo,
    String? timezone,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/billing/summary',
      queryParameters: _dateQuery(dateFrom, dateTo, timezone),
    );
    return BillingSummary.fromJson(response.data ?? const {});
  }

  Future<PagedResult<UsageEntry>> getUsage({
    required int page,
    int pageSize = 20,
    DateTime? dateFrom,
    DateTime? dateTo,
    String? timezone,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/billing/usage',
      queryParameters: {
        'page': page,
        'page_size': pageSize,
        ..._dateQuery(dateFrom, dateTo, timezone),
      },
    );
    return PagedResult.fromJson(response.data ?? const {}, UsageEntry.fromJson);
  }

  Future<List<PaymentProviderInfo>> getProviders() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/billing/providers',
    );
    return (response.data?['items'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(PaymentProviderInfo.fromJson)
        .toList();
  }

  Future<PagedResult<PaymentOrder>> getOrders({
    required int page,
    int pageSize = 10,
    String? status,
    String? provider,
    String? orderId,
    DateTime? dateFrom,
    DateTime? dateTo,
    String? timezone,
  }) async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/billing/orders',
      queryParameters: {
        'page': page,
        'page_size': pageSize,
        if (status?.isNotEmpty ?? false) 'status': status,
        if (provider?.isNotEmpty ?? false) 'provider': provider,
        if (orderId?.isNotEmpty ?? false) 'order_id': orderId,
        ..._dateQuery(dateFrom, dateTo, timezone),
      },
    );
    return PagedResult.fromJson(
      response.data ?? const {},
      PaymentOrder.fromJson,
    );
  }

  Future<PaymentOrder> createTopupOrder({
    required String provider,
    required int amountFen,
    required String requestKey,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/billing/orders',
      data: {
        'provider': provider,
        'kind': 'topup',
        'amount_fen': amountFen,
        'request_key': requestKey,
      },
    );
    return PaymentOrder.fromJson(response.data ?? const {});
  }

  Future<PaymentOrder> createSubscriptionOrder({
    required String provider,
    required String planId,
    required String cycle,
    required String requestKey,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/billing/orders',
      data: {
        'provider': provider,
        'kind': 'subscription',
        'plan_id': planId,
        'cycle': cycle,
        'request_key': requestKey,
      },
    );
    return PaymentOrder.fromJson(response.data ?? const {});
  }

  Future<PaymentOrder> continueOrder(String orderId) =>
      _orderAction(orderId, 'checkout');

  Future<NativeAppCheckout> createAppCheckout(String orderId) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/billing/orders/${Uri.encodeComponent(orderId)}/app-checkout',
    );
    return NativeAppCheckout.fromJson(response.data ?? const {});
  }

  Future<PaymentOrder> refreshOrder(String orderId) =>
      _orderAction(orderId, 'refresh');

  Future<PaymentOrder> cancelOrder(String orderId) =>
      _orderAction(orderId, 'cancel');

  Future<PaymentOrder> _orderAction(String orderId, String action) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/billing/orders/${Uri.encodeComponent(orderId)}/$action',
    );
    return PaymentOrder.fromJson(response.data ?? const {});
  }

  Map<String, Object> _dateQuery(
    DateTime? dateFrom,
    DateTime? dateTo,
    String? timezone,
  ) => {
    if (dateFrom != null) 'date_from': _date(dateFrom),
    if (dateTo != null) 'date_to': _date(dateTo),
    if (timezone?.isNotEmpty ?? false) 'tz': timezone!,
  };

  String _date(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

final billingApiProvider = Provider<BillingApi>(
  (ref) => BillingApi(ref.watch(apiDioProvider)),
);
