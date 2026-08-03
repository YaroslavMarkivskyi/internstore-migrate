import { IProductPublic } from '../products/interfaces';

// The backend cart (services/orders) only stores {product_id, quantity} per
// item — no cart-level totals/timestamps and no per-item id, price or
// product snapshot. totalCost/itemsCount/createdAt/updatedAt and the
// nested `product` below are all composed client-side in
// services/http/public/cart.ts from GET /cart plus a per-product lookup;
// totalCost reflects *current* product prices, not the price at add-time.
export interface ICart {
  id: number;
  totalCost: string;
  itemsCount: number;
  createdAt: Date;
  updatedAt: Date;
}

export interface ICartItem {
  id: string;
  quantity: number;
  product: IProductPublic;
}
