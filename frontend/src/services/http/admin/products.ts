import { ProductFormDataOutput } from '@components/ProductForm/schema';
import { fetchCategories } from '@services/http/catalog';

import { ccApi as api } from '../api';

import { ICategory } from '../../../types/categories/interfaces';
import { PaginatedResults } from '../../../types/pagination/interfaces';
import {
  IProductAdmin,
  IProductFilterParamsAdmin,
  IProductFiltersMetaAdmin,
  IProductImage,
} from '../../../types/products/interfaces';
import { IStocksDetails } from '../../../types/stocks/interfaces';

// Catalog has no pagination/filtering/"totalQuantity" concept of its own
// (that last one is Inventory's) -- everything below composes the admin
// product list from Catalog's flat GET /products, Inventory's per-product
// quantity aggregate (GET /items, already grouped by product_id server
// side), and Catalog's own categories, same client-side-composition
// pattern services/http/public/products.ts uses for the customer list.

interface CatalogProductRaw {
  id: string;
  name: string;
  price: number;
  categoryId: string;
  description: string | null;
  minTemperature: number | null;
  maxTemperature: number | null;
  isPublished: boolean;
}

interface InventoryConsolidatedItem {
  productId: string;
  quantity: number;
}

const fetchCatalogProducts = async (): Promise<CatalogProductRaw[]> => {
  const resp = await api.get<CatalogProductRaw[]>('catalog/products');
  return resp.data;
};

const fetchInventoryQuantities = async (): Promise<Map<string, number>> => {
  const resp = await api.get<InventoryConsolidatedItem[]>('inventory/items');
  return new Map(resp.data.map(item => [item.productId, item.quantity]));
};

const toProductAdmin = (
  raw: CatalogProductRaw,
  categories: ICategory[],
  quantityByProduct: Map<string, number>
): IProductAdmin => ({
  id: raw.id,
  name: raw.name,
  price: raw.price.toFixed(2),
  description: raw.description ?? '',
  category: categories.find(category => category.id === raw.categoryId),
  minTemperature: raw.minTemperature ?? 0,
  maxTemperature: raw.maxTemperature ?? 0,
  isPublished: raw.isPublished,
  totalQuantity: quantityByProduct.get(raw.id) ?? 0,
});

const fetchAllProductsAdmin = async (): Promise<IProductAdmin[]> => {
  const [rawProducts, categories, quantities] = await Promise.all([
    fetchCatalogProducts(),
    fetchCategories(),
    fetchInventoryQuantities(),
  ]);
  return rawProducts.map(raw => toProductAdmin(raw, categories, quantities));
};

export const getProduct = async (productId: string): Promise<IProductAdmin> => {
  const [raw, categories, quantities] = await Promise.all([
    api.get<CatalogProductRaw>(`catalog/products/${productId}`).then(resp => resp.data),
    fetchCategories(),
    fetchInventoryQuantities(),
  ]);
  return toProductAdmin(raw, categories, quantities);
};

// Catalog's GET /products returns the *entire* list, unpaginated and
// unfiltered (see internstore-migrate/services/catalog/src/catalog/routers/products.py)
// -- filtering, ordering and pagination are all applied here, client-side,
// same as public/products.ts does for the customer list.
export const getProducts = async (
  filterParams: IProductFilterParamsAdmin
): Promise<PaginatedResults<IProductAdmin>> => {
  let products = await fetchAllProductsAdmin();

  if (filterParams.search) {
    const search = filterParams.search.toLowerCase();
    products = products.filter(product =>
      product.name.toLowerCase().includes(search)
    );
  }
  if (filterParams.category?.length) {
    const categorySet = new Set(filterParams.category);
    products = products.filter(
      product => product.category && categorySet.has(product.category.id)
    );
  }
  if (filterParams.isPublished !== undefined) {
    products = products.filter(
      product => product.isPublished === filterParams.isPublished
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
  if (filterParams.totalQuantityMin !== undefined) {
    products = products.filter(
      product => product.totalQuantity >= filterParams.totalQuantityMin!
    );
  }
  if (filterParams.totalQuantityMax !== undefined) {
    products = products.filter(
      product => product.totalQuantity <= filterParams.totalQuantityMax!
    );
  }
  if (filterParams.ordering) {
    const desc = filterParams.ordering.startsWith('-');
    const field = desc ? filterParams.ordering.slice(1) : filterParams.ordering;
    products = [...products].sort((a, b) => {
      const aVal = field === 'price' ? Number(a.price) : a.totalQuantity;
      const bVal = field === 'price' ? Number(b.price) : b.totalQuantity;
      return (aVal - bVal) * (desc ? -1 : 1);
    });
  }

  const count = products.length;
  const offset = filterParams.offset ?? 0;
  const limit = filterParams.limit ?? count;
  const results = products.slice(offset, offset + limit);

  return { count, results };
};

export const getProductFiltersMeta = async (): Promise<IProductFiltersMetaAdmin> => {
  const products = await fetchAllProductsAdmin();
  const prices = products.map(product => Number(product.price));
  const quantities = products.map(product => product.totalQuantity);
  return {
    minPrice: (prices.length ? Math.min(...prices) : 0).toFixed(2),
    maxPrice: (prices.length ? Math.max(...prices) : 0).toFixed(2),
    minQuantity: quantities.length ? Math.min(...quantities) : 0,
    maxQuantity: quantities.length ? Math.max(...quantities) : 0,
  };
};

interface CatalogProductPayload {
  name: string;
  price: number;
  categoryId: string;
  description?: string;
  minTemperature?: number;
  maxTemperature?: number;
}

const toCatalogPayload = (
  productData: ProductFormDataOutput
): CatalogProductPayload => ({
  name: productData.name,
  price: Number(productData.price),
  categoryId: productData.category,
  description: productData.description,
  minTemperature: productData.minTemperature,
  maxTemperature: productData.maxTemperature,
});

export const addProduct = async (
  productData: ProductFormDataOutput
): Promise<IProductAdmin> => {
  const created = await api.post<CatalogProductRaw>(
    'catalog/products',
    toCatalogPayload(productData)
  );
  const [categories, quantities] = await Promise.all([
    fetchCategories(),
    fetchInventoryQuantities(),
  ]);
  const product = toProductAdmin(created.data, categories, quantities);

  const photosToUpload = productData.photos?.filter(
    (photo): photo is File => photo instanceof File
  );
  if (photosToUpload?.length) {
    try {
      await addImages(photosToUpload, product.id);
    } catch (e: unknown) {
      // Recover: the product was just created in this same call and has
      // no images to lose yet, so it's safe to unpublish + delete it if
      // the images that were supposed to come with it failed to upload.
      await api.patch(`catalog/products/${product.id}`, { isPublished: false });
      await deleteProduct(product.id);
      throw e;
    }
  }
  return product;
};

export const editProduct = async (
  productId: string,
  productData: ProductFormDataOutput
): Promise<IProductAdmin> => {
  const updated = await api.patch<CatalogProductRaw>(
    `catalog/products/${productId}`,
    toCatalogPayload(productData)
  );
  const [categories, quantities] = await Promise.all([
    fetchCategories(),
    fetchInventoryQuantities(),
  ]);
  const product = toProductAdmin(updated.data, categories, quantities);

  // Unlike addProduct's rollback, a failed image update here must NOT
  // delete the product -- it already existed before this call, with its
  // own history (stock, orders); the field edit above already succeeded
  // and should stand even if the image step fails.
  if (productData.photosToDelete.length) {
    await deleteImages(
      productId,
      productData.photosToDelete.map(image => image.id)
    );
  }
  const photosToUpload = productData.photos?.filter(
    (photo): photo is File => photo instanceof File
  );
  if (photosToUpload?.length) {
    await addImages(photosToUpload, productId);
  }
  return product;
};

export const getImages = async (productId: string): Promise<IProductImage[]> => {
  const resp = await api.get<IProductImage[]>(
    `catalog/products/${productId}/images`
  );
  return resp.data;
};

// One multipart POST per file -- Catalog's upload endpoint takes a single
// file per request, same as Chat's attachment upload.
export const addImages = async (
  images: File[],
  productId: string
): Promise<IProductImage[]> => {
  const uploaded: IProductImage[] = [];
  for (const image of images) {
    const form = new FormData();
    form.append('file', image);
    const resp = await api.post<IProductImage>(
      `catalog/products/${productId}/images`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    uploaded.push(resp.data);
  }
  return uploaded;
};

export const deleteImages = async (
  productId: string,
  imageIds: string[]
): Promise<void> => {
  await Promise.all(
    imageIds.map(imageId =>
      api.delete(`catalog/products/${productId}/images/${imageId}`)
    )
  );
};

export const deleteProduct = async (productId: string): Promise<void> => {
  await api.delete(`catalog/products/${productId}`);
};

export const updateProductCategory = async (
  productId: string,
  categoryId: string
): Promise<IProductAdmin> => {
  const updated = await api.patch<CatalogProductRaw>(
    `catalog/products/${productId}`,
    { categoryId }
  );
  const [categories, quantities] = await Promise.all([
    fetchCategories(),
    fetchInventoryQuantities(),
  ]);
  return toProductAdmin(updated.data, categories, quantities);
};

export const toggleProductPublish = async (
  productId: string,
  data: unknown
): Promise<IProductAdmin> => {
  const updated = await api.patch<CatalogProductRaw>(
    `catalog/products/${productId}`,
    data
  );
  const [categories, quantities] = await Promise.all([
    fetchCategories(),
    fetchInventoryQuantities(),
  ]);
  return toProductAdmin(updated.data, categories, quantities);
};

interface StockItemDetailRaw {
  id: string;
  stockId: string;
  name: string;
  quantity: number;
  temperature: number | null;
  humidity: number | null;
}

// Admin/Stocks' per-stock breakdown for one product -- Inventory has no
// per-product aggregate of its own to reuse, so this hits the same
// /items/detailed endpoint stockService.ts uses for the stock-scoped
// tables, filtered to a single product_id.
export const getStocksDetails = async (
  productId: string
): Promise<IStocksDetails> => {
  const resp = await api.get<StockItemDetailRaw[]>('inventory/items/detailed', {
    params: { productId },
  });
  return { stocks: resp.data };
};
