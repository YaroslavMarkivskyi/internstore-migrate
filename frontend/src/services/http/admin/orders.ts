import { isAxiosError } from 'axios';

import { ccApi as api } from '@services/http/api';
import { fetchCategories, fetchProduct, toProductPublic } from '@services/http/catalog';

import {
  IOrderAdmin,
  IOrderItemAdmin,
  IOrderItemPublic,
  IOrderItemsFilters,
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
interface OrderAdminRaw {
  id: string;
  status: OrderStatus;
  contactName: string;
  contactEmail: string;
  contactPhone: string | null;
  paymentMethod: string;
  createdAt: string;
  customer: string;
  items: OrderItemRaw[];
}

// Mirrors toContactInfo/toOrderItems in
// internstore-migrate/frontend/src/services/http/public/orders.ts — the
// backend admin order shape (internstore-migrate/services/orders/src/orders/schemas.py
// OrderAdminRead) only adds a `customer` field on top of the public one, so
// the same client-side enrichment (price/product looked up from Catalog)
// applies here.
// Orders keeps no product snapshot (see OrderAdminRaw above), so an item
// referencing a product that's since been deleted from Catalog 404s here.
// A single such item used to reject the whole Promise.all, blanking out
// the entire order (and, since getOrders maps every order through this,
// the entire admin Orders list) — dropped instead, so the rest of the
// order still renders.
const toOrderItems = async (raw: OrderAdminRaw): Promise<IOrderItemPublic[]> => {
  const categories = await fetchCategories();
  const items = await Promise.all(
    raw.items.map(async item => {
      try {
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
      } catch (error) {
        if (isAxiosError(error) && error.response?.status === 404) {
          return null;
        }
        throw error;
      }
    })
  );
  return items.flatMap(item => (item === null ? [] : [item]));
};

const toOrderAdmin = async (raw: OrderAdminRaw): Promise<IOrderAdmin> => {
  const items = await toOrderItems(raw);
  return {
    id: raw.id,
    status: raw.status,
    createdAt: new Date(raw.createdAt),
    itemsAmount: items.reduce((sum, item) => sum + item.quantity, 0),
    totalCost: items
      .reduce((sum, item) => sum + Number(item.totalPrice), 0)
      .toFixed(2),
    contactInfo: {
      id: 0,
      firstName: raw.contactName,
      lastName: '',
      phone: raw.contactPhone ?? '',
      email: raw.contactEmail,
      deliveryAddress: '',
    },
    customer: raw.customer,
  };
};

// GET /orders/admin returns the full unpaginated list (admin-only, see
// orders_admin.py) — pagination is applied client-side, same as
// public/orders.ts. Status/date/archived/ordering filters aren't supported
// by the backend yet, so they're a no-op here.
export const getOrders = async (
  filterParams: PaginationQueryParams
): Promise<PaginatedResults<IOrderAdmin>> => {
  const resp = await api.get<OrderAdminRaw[]>('orders/admin');
  const orders = await Promise.all(resp.data.map(toOrderAdmin));

  const offset = filterParams.offset ?? 0;
  const limit = filterParams.limit ?? orders.length;
  return { count: orders.length, results: orders.slice(offset, offset + limit) };
};

export const getOrder = async (orderId: string): Promise<IOrderAdmin> => {
  const resp = await api.get<OrderAdminRaw>(`orders/admin/${orderId}`);
  return toOrderAdmin(resp.data);
};

// Manual counterpart to Stripe's webhook-driven confirmation (card orders
// go through StripePaymentStep + payments.py instead) — for
// cash_on_delivery, there's no processor to confirm payment for us, so an
// admin marks it paid once the cash is actually collected. Backend doesn't
// restrict this to cash_on_delivery orders specifically (see
// pay_order_admin in orders_admin.py), just pending -> paid like any other
// payment confirmation.
export const payOrder = async (orderId: string): Promise<IOrderAdmin> => {
  const resp = await api.post<OrderAdminRaw>(`orders/admin/${orderId}/pay`);
  return toOrderAdmin(resp.data);
};

interface InventoryConsolidatedItem {
  productId: string;
  quantity: number;
}

// No separate order-items endpoint — items are already embedded in
// GET /orders/admin/{id}, so this just fetches the order and paginates its
// items client-side (same pattern as public/orders.ts's getOrderItems).
// availableQuantity comes from Inventory's consolidated-items endpoint
// (already used by admin/products.ts), since Orders itself doesn't track
// stock levels.
export const getOrderItems = async (
  orderId: string,
  filterParams: IOrderItemsFilters
): Promise<PaginatedResults<IOrderItemAdmin>> => {
  const [orderResp, inventoryResp] = await Promise.all([
    api.get<OrderAdminRaw>(`orders/admin/${orderId}`),
    api.get<InventoryConsolidatedItem[]>('inventory/items'),
  ]);
  const availableQuantities = new Map(
    inventoryResp.data.map(item => [item.productId, item.quantity])
  );

  const items: IOrderItemAdmin[] = (await toOrderItems(orderResp.data)).map(
    item => ({
      ...item,
      availableQuantity: availableQuantities.get(item.product.id) ?? 0,
    })
  );

  const offset = filterParams.offset ?? 0;
  const limit = filterParams.limit ?? items.length;
  return { count: items.length, results: items.slice(offset, offset + limit) };
};
