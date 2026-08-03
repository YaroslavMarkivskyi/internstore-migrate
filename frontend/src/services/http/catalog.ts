
import { ICategory } from '../../types/categories/interfaces';
import { IProductPublic } from '../../types/products/interfaces';

import { ccApi as api } from './api';

// Shared low-level access to the Catalog service (/api/catalog/*) —
// products.ts, categories.ts, cart.ts and orders.ts all need to look up
// product/category data, so the raw fetch + response shape lives here once.
// ccApi (axios-case-converter) already turns the backend's snake_case
// fields (category_id, min_temperature...) into camelCase for us.
export interface CatalogProductRaw {
  id: string;
  name: string;
  price: number;
  categoryId: string;
  description: string | null;
  minTemperature: number | null;
  maxTemperature: number | null;
}

export const fetchCategories = async (): Promise<ICategory[]> => {
  const resp = await api.get<ICategory[]>('catalog/categories');
  return resp.data;
};

export const fetchProducts = async (): Promise<CatalogProductRaw[]> => {
  const resp = await api.get<CatalogProductRaw[]>('catalog/products');
  return resp.data;
};

export const fetchProduct = async (
  productId: string
): Promise<CatalogProductRaw> => {
  const resp = await api.get<CatalogProductRaw>(`catalog/products/${productId}`);
  return resp.data;
};

// The catalog service has no inventory/image data wired to it yet (see the
// connection gap list) — inStock/image can't be sourced from the backend,
// so callers get a fixed default rather than a fabricated real value.
export const toProductPublic = (
  raw: CatalogProductRaw,
  categories: ICategory[]
): IProductPublic => ({
  id: raw.id,
  name: raw.name,
  price: raw.price.toFixed(2),
  description: raw.description ?? '',
  category: categories.find(category => category.id === raw.categoryId),
  inStock: true,
});
