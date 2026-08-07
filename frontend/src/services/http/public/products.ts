import {
  fetchCategories,
  fetchProduct,
  fetchProducts,
  toProductPublic,
} from '../catalog';

import { PaginatedResults } from 'src/types/pagination/interfaces';
import {
  IProductFilterParamsPublic,
  IProductFiltersMetaPublic,
  IProductPublic,
} from 'src/types/products/interfaces';

// Catalog's GET /products returns the *entire* list with no filtering,
// search, ordering or pagination support server-side (see
// internstore-migrate/services/catalog/src/catalog/routers/products.py) —
// all of that is applied here, client-side, against the full list.
export const getProducts = async (
  filterParams: IProductFilterParamsPublic
): Promise<PaginatedResults<IProductPublic>> => {
  const [rawProducts, categories] = await Promise.all([
    fetchProducts(),
    fetchCategories(),
  ]);

  // Catalog's GET /products makes no distinction between admin and public
  // callers (see admin/products.ts's own separate fetch of the same
  // endpoint, which deliberately keeps unpublished products for editing)
  // -- filtering unpublished/out-of-stock-unpublished products out of
  // customer-facing browsing surfaces is entirely this layer's job.
  let products = rawProducts
    .filter(raw => raw.isPublished)
    .map(raw => toProductPublic(raw, categories));

  if (filterParams.ids?.length) {
    const idSet = new Set(filterParams.ids);
    products = products.filter(product => idSet.has(product.id));
  }
  if (filterParams.category?.length) {
    const categorySet = new Set(filterParams.category);
    products = products.filter(
      product => product.category && categorySet.has(product.category.id)
    );
  }
  if (filterParams.search) {
    const search = filterParams.search.toLowerCase();
    products = products.filter(product =>
      product.name.toLowerCase().includes(search)
    );
  }
  if (filterParams.priceMin !== undefined) {
    products = products.filter(
      product => Number(product.price) >= filterParams.priceMin!
    );
  }
  if (filterParams.priceMax !== undefined) {
    products = products.filter(
      product => Number(product.price) <= filterParams.priceMax!
    );
  }
  if (filterParams.ordering) {
    const desc = filterParams.ordering.startsWith('-');
    products = [...products].sort(
      (a, b) => (Number(a.price) - Number(b.price)) * (desc ? -1 : 1)
    );
  }

  const count = products.length;
  const offset = filterParams.offset ?? 0;
  const limit = filterParams.limit ?? count;
  const page = products.slice(offset, offset + limit);

  return { count, results: page };
};

export const getProduct = async (
  productId: string
): Promise<IProductPublic> => {
  const [raw, categories] = await Promise.all([
    fetchProduct(productId),
    fetchCategories(),
  ]);
  return toProductPublic(raw, categories);
};

export const getProductFiltersMeta = async (): Promise<IProductFiltersMetaPublic> => {
  const products = await fetchProducts();
  const prices = products.map(product => product.price);
  const minPrice = prices.length ? Math.min(...prices) : 0;
  const maxPrice = prices.length ? Math.max(...prices) : 0;
  return { minPrice: minPrice.toFixed(2), maxPrice: maxPrice.toFixed(2) };
};
