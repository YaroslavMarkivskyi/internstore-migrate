import { ccApi as api } from '@services/http/api';
import {
  fetchCategories,
  fetchProduct,
  toProductPublic,
} from '@services/http/catalog';

import { ICart, ICartItem } from '../../../types/cart/interfaces';
import {
  PaginatedResults,
  PaginationQueryParams,
} from '../../../types/pagination/interfaces';

interface CartItemRaw {
  productId: string;
  quantity: number;
}
interface CartRaw {
  items: CartItemRaw[];
}

// Orders' cart only stores {product_id, quantity} per item (see
// internstore-migrate/services/orders/src/orders/schemas.py) — no per-item
// id, price snapshot or product data, and no cart-level totals/timestamps.
// Both are composed here by looking up each product individually.
const toCartItems = async (raw: CartRaw): Promise<ICartItem[]> => {
  const categories = await fetchCategories();
  return Promise.all(
    raw.items.map(async item => {
      const product = await fetchProduct(item.productId);
      return {
        id: item.productId,
        quantity: item.quantity,
        product: toProductPublic(product, categories),
      };
    })
  );
};

const toCart = (items: ICartItem[]): ICart => ({
  id: 0,
  itemsCount: items.length,
  // Reflects current product prices, not the price at the time each item
  // was added — the backend keeps no such history.
  totalCost: items
    .reduce((sum, item) => sum + Number(item.product.price) * item.quantity, 0)
    .toFixed(2),
  createdAt: new Date(),
  updatedAt: new Date(),
});

const fetchCartRaw = async (): Promise<CartRaw> => {
  const resp = await api.get<CartRaw>('orders/cart');
  return resp.data;
};

export const getCart = async (): Promise<ICart> => {
  const items = await toCartItems(await fetchCartRaw());
  return toCart(items);
};

export const getCartItem = async (
  productId: string
): Promise<ICartItem | undefined> => {
  const items = await toCartItems(await fetchCartRaw());
  return items.find(item => item.id === productId);
};

// Cart has no server-side pagination — filterParams is accepted only to
// keep the existing call sites working, and is otherwise ignored.
export const getCartItems = async (
  _filterParams?: PaginationQueryParams
): Promise<PaginatedResults<ICartItem>> => {
  const items = await toCartItems(await fetchCartRaw());
  return { count: items.length, results: items };
};

export const addItemToCart = async (productId: string): Promise<void> => {
  await api.post('orders/cart', { productId, quantity: 1 });
};

export const updateCartItemQuantity = async (
  productId: string,
  quantity: number
): Promise<void> => {
  await api.put(`orders/cart/items/${productId}`, { quantity });
};

export const removeItemFromCart = async (productId: string): Promise<void> => {
  await api.delete(`orders/cart/items/${productId}`);
};

// The backend has no cart-merge endpoint — a guest's pre-login cart (tied to
// the guest_id from auth-backend's guest session, see
// internstore-migrate/services/auth-backend/README.md) is not carried over
// to the authenticated account. This is a no-op so login itself doesn't
// fail because of it.
export const mergeCart = async (_accessToken: string): Promise<void> => {};
