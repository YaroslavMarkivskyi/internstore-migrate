import { ccApi } from '@services/http/api';
import { toQueryParams } from '@utils/toQueryParams';

import {
  IOrderAdmin,
  IOrderItemAdmin,
  IOrderItemsFilters,
} from '../../../types/orders/interfaces';
import {
  PaginatedResults,
  PaginationQueryParams,
} from '../../../types/pagination/interfaces';

// No admin-specific orders namespace on the backend (only the customer-
// scoped GET /orders, filtered by the caller's own claims — see
// internstore-migrate/services/orders/src/orders/routers/orders.py). These
// calls are left as-is and will 404 until an admin view exists there.
export const getOrders = async (filterParams: PaginationQueryParams) => {
  const queryParams = toQueryParams<PaginationQueryParams>(filterParams);
  const resp = await ccApi.get<PaginatedResults<IOrderAdmin>>(
    `admin/orders/${queryParams}`
  );
  return resp.data;
};

export const getOrder = async (orderId: string) => {
  const resp = await ccApi.get<IOrderAdmin>(`admin/orders/${orderId}/`);
  return resp.data;
};

export const getOrderItems = async (
  orderId: string,
  filterParams: IOrderItemsFilters
) => {
  const queryParams = toQueryParams<IOrderItemsFilters>(filterParams);
  const resp = await ccApi.get<PaginatedResults<IOrderItemAdmin>>(
    `admin/orders/${orderId}/products/${queryParams}`
  );
  return resp.data;
};
