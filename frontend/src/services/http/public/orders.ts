import { ccApi as api } from '@services/http/api';
import { fetchCategories, fetchProduct, toProductPublic } from '@services/http/catalog';

import {
  IContactInfo,
  IOrderItemPublic,
  IOrderPublic,
} from '../../../types/orders/interfaces';
import { OrderStatus } from '../../../types/orders/types';
import {
  PaginatedResults,
  PaginationQueryParams,
} from '../../../types/pagination/interfaces';

interface OrderItemRaw {
  productId: string;
  quantity: number;
}
interface OrderRaw {
  id: string;
  status: OrderStatus;
  contactName: string;
  contactEmail: string;
  contactPhone: string | null;
  paymentMethod: string;
  createdAt: string;
  items: OrderItemRaw[];
}

// Backend orders have a single contact_name (no first/last split) and no
// delivery address at all — see CheckoutRequest/OrderRead in
// internstore-migrate/services/orders/src/orders/schemas.py.
const toContactInfo = (raw: OrderRaw): IContactInfo => ({
  id: 0,
  firstName: raw.contactName,
  lastName: '',
  phone: raw.contactPhone ?? '',
  email: raw.contactEmail,
  deliveryAddress: '',
});

// Order items are only {product_id, quantity} on the backend — price and
// totalPrice below are approximated from the product's *current* price,
// not the price actually paid at order time (the backend keeps no such
// record).
const toOrderItems = async (raw: OrderRaw): Promise<IOrderItemPublic[]> => {
  const categories = await fetchCategories();
  return Promise.all(
    raw.items.map(async item => {
      const product = await fetchProduct(item.productId);
      const productPublic = toProductPublic(product, categories);
      const totalPrice = (Number(productPublic.price) * item.quantity).toFixed(2);
      return {
        id: item.productId,
        product: productPublic,
        quantity: item.quantity,
        price: productPublic.price,
        totalPrice,
      };
    })
  );
};

const toOrderPublic = async (raw: OrderRaw): Promise<IOrderPublic> => {
  const items = await toOrderItems(raw);
  return {
    id: raw.id,
    status: raw.status,
    createdAt: new Date(raw.createdAt),
    itemsAmount: items.reduce((sum, item) => sum + item.quantity, 0),
    totalCost: items
      .reduce((sum, item) => sum + Number(item.totalPrice), 0)
      .toFixed(2),
    contactInfo: toContactInfo(raw),
  };
};

// GET /orders returns the full unpaginated list — pagination is applied
// client-side (see internstore-migrate/services/orders/src/orders/routers/orders.py).
export const getOrders = async (
  filterParams: PaginationQueryParams
): Promise<PaginatedResults<IOrderPublic>> => {
  const resp = await api.get<OrderRaw[]>('orders/orders');
  const orders = await Promise.all(resp.data.map(toOrderPublic));

  const offset = filterParams.offset ?? 0;
  const limit = filterParams.limit ?? orders.length;
  return { count: orders.length, results: orders.slice(offset, offset + limit) };
};

// No separate order-items endpoint — items are already embedded in
// GET /orders/{id}, so this just fetches the order and paginates its items
// client-side.
export const getOrderItems = async (
  orderId: string,
  filterParams: PaginationQueryParams
): Promise<PaginatedResults<IOrderItemPublic>> => {
  const resp = await api.get<OrderRaw>(`orders/orders/${orderId}`);
  const items = await toOrderItems(resp.data);

  const offset = filterParams.offset ?? 0;
  const limit = filterParams.limit ?? items.length;
  return { count: items.length, results: items.slice(offset, offset + limit) };
};

export interface CheckoutPayload {
  contactName: string;
  contactEmail: string;
  contactPhone?: string;
  paymentMethod: string;
}

export const checkout = async (
  payload: CheckoutPayload
): Promise<IOrderPublic> => {
  const resp = await api.post<OrderRaw>('orders/checkout', payload);
  return toOrderPublic(resp.data);
};
