import { PaginationQueryParams } from '../pagination/interfaces';
import { IProductShort } from '../products/interfaces';

import {
  DateRange,
  OrderOrdering,
  OrderProductOrdering,
  OrderStatus,
} from './types';

// The backend order (services/orders) stores a single contact_name (not
// split first/last) and no delivery address at all — see
// CheckoutRequest/OrderRead in
// internstore-migrate/services/orders/src/orders/schemas.py.
// contactInfo below is composed client-side; lastName/deliveryAddress are
// always empty since the backend has nothing to put there.
export interface IContactInfo {
  id: number;
  firstName: string;
  lastName: string;
  phone: string;
  email: string;
  deliveryAddress: string;
}

// Backend order items are only {product_id, quantity} — no id, price or
// product snapshot. price/totalPrice here are computed client-side from
// the product's *current* price, not the price actually paid at order
// time — see services/http/public/orders.ts.
export interface IOrderItemPublic {
  id: string;
  product: IProductShort;
  quantity: number;
  price: string;
  totalPrice: string;
}

export interface IOrderItemAdmin extends IOrderItemPublic {
  availableQuantity: number;
}

export interface IOrderPublic {
  id: string;
  status: OrderStatus;
  createdAt: Date;
  totalCost: string;
  itemsAmount: number;
  contactInfo: IContactInfo;
}

export interface IOrderAdmin extends IOrderPublic {
  customer: number | null;
}

export interface IOrderItemsFilters extends PaginationQueryParams {
  ordering?: OrderProductOrdering;
}

export interface IOrdersFilterParamsAdmin extends PaginationQueryParams {
  archived?: boolean;
  status?: OrderStatus[];
  date?: DateRange[];
  ordering?: OrderOrdering;
}

export interface IOrdersFilterParamsAdminRaw
  extends Omit<IOrdersFilterParamsAdmin, 'date'> {
  date?: string;
}
