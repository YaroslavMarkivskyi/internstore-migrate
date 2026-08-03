import { ccApi } from '@services/http/api';
import { fetchCategories, fetchProducts, toProductPublic } from '@services/http/catalog';

import {
  ICategory,
  ICategoryPreview,
} from '../../../types/categories/interfaces';
import { PaginatedResults } from '../../../types/pagination/interfaces';
import { IProductPublic } from '../../../types/products/interfaces';

export const getCategories = async () => {
  return await fetchCategories();
};

export const getCategoriesWithProductCounts = async () => {
  return await getCategories();
};

// Catalog has no GET /categories/{id}/products endpoint — derived here from
// the full product list, filtered by category, with pagination applied
// client-side (see internstore-migrate/services/catalog/src/catalog/routers).
export const getCategoryProducts = async (
  categoryId: string,
  page: number = 1,
  pageSize: number = 8
): Promise<PaginatedResults<IProductPublic>> => {
  const [rawProducts, categories] = await Promise.all([
    fetchProducts(),
    fetchCategories(),
  ]);
  const products = rawProducts
    .filter(raw => raw.categoryId === categoryId)
    .map(raw => toProductPublic(raw, categories));

  const start = (page - 1) * pageSize;
  return {
    count: products.length,
    results: products.slice(start, start + pageSize),
  };
};

export const createCategory = async (name: string): Promise<ICategory> => {
  const resp = await ccApi.post<ICategory>('catalog/categories', { name });
  return resp.data;
};

// Not implemented on the backend — Catalog only has GET/POST /categories,
// no PATCH/DELETE (see internstore-migrate/services/catalog/src/catalog/routers/categories.py).
export const updateCategory = async (
  _categoryId: string,
  _name: string
): Promise<never> => {
  throw new Error('Editing categories is not supported by the backend yet.');
};

export const deleteCategory = async (
  _categoryId: string,
  _options?: {
    deletionMode?: 'move' | 'unpublish_and_delete';
    targetCategoryId?: string;
  }
): Promise<never> => {
  throw new Error('Deleting categories is not supported by the backend yet.');
};

// No preview-image support in the backend yet — every category comes back
// with image: null rather than a fabricated URL.
export const getCategoriesPreview = async (): Promise<ICategoryPreview[]> => {
  const categories = await fetchCategories();
  return categories.map(category => ({ ...category, image: null }));
};
