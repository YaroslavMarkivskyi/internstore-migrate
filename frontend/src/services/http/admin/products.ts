import { ProductFormDataOutput } from '@components/ProductForm/schema';
import { toQueryParams } from '@utils/toQueryParams';

import api, { toFormData } from '../api';

import { PaginatedResults } from '../../../types/pagination/interfaces';
import {
  IProductAdmin,
  IProductFilterParamsAdmin,
  IProductFiltersMetaAdmin,
  IProductImage,
} from '../../../types/products/interfaces';
import { IStocksDetails } from '../../../types/stocks/interfaces';

// Admin product management beyond create/publish-toggle (images, delete,
// full edit, filters_meta, per-product stock summary) has no backend
// support yet — see internstore-migrate/services/catalog/src/catalog/routers/products.py,
// which only has GET/POST /products and PATCH /products/{id}. These calls
// are left pointed at their old paths and will 404 until that lands; ids
// below are strings (UUIDs) to match the catalog service.

export const getProduct = async (productId: string) => {
  const resp = await api.get<IProductAdmin>(`admin/products/${productId}/`);
  return resp.data;
};

export const getProducts = async (filterParams: IProductFilterParamsAdmin) => {
  const queryParams = toQueryParams<IProductFilterParamsAdmin>(filterParams);
  const resp = await api.get<PaginatedResults<IProductAdmin>>(
    `admin/products/${queryParams}`
  );
  return resp.data;
};

export const addProduct = async (productData: ProductFormDataOutput) => {
  const resp = await api.post<IProductAdmin>('admin/products/', productData);
  const photosToUpload = productData.photos?.filter(
    photo => photo instanceof File
  );
  if (photosToUpload?.length) {
    try {
      await addImages(photosToUpload, resp.data.id);
    } catch (e: unknown) {
      // Recover: if any error, delete created product
      await deleteProduct(resp.data.id);
      throw e;
    }
  }
  return resp.data;
};

export const editProduct = async (
  productId: string,
  productData: ProductFormDataOutput
) => {
  const resp = await api.put<IProductAdmin>(
    `admin/products/${productId}/`,
    productData
  );
  try {
    if (productData.photosToDelete.length) {
      await deleteImages(
        resp.data.id,
        productData.photosToDelete.map(image => image.id)
      );
    }
    const photosToUpload = productData.photos?.filter(
      photo => photo instanceof File
    );
    if (photosToUpload?.length) {
      await addImages(photosToUpload, resp.data.id);
    }
  } catch (e: unknown) {
    // Recover: if any error, delete created product
    await deleteProduct(resp.data.id);
    throw e;
  }
  return resp.data;
};

export const getImages = async (productId: string) => {
  const resp = await api.get<IProductImage[]>(
    `admin/products/${productId}/images/`
  );
  return resp.data;
};

export const addImages = async (images: File[], productId: string) => {
  const form = toFormData({ images }, ['images']);
  const resp = await api.post<File>(
    `admin/products/${productId}/images/`,
    form,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return resp.data;
};

export const deleteImages = async (productId: string, imageIds: number[]) => {
  const resp = await api.post(
    `admin/products/${productId}/images/bulk-delete/`,
    {
      imageIds,
    }
  );
  return resp.data;
};

export const deleteProduct = async (productId: string) => {
  const resp = await api.delete(`admin/products/${productId}/`);
  return resp.data;
};

export const updateProductCategory = async (
  productId: string,
  categoryId: string
) => {
  const resp = await api.patch<IProductAdmin>(`admin/products/${productId}/`, {
    category: categoryId,
  });
  return resp.data;
};

export const getProductFiltersMeta = async () => {
  const resp = await api.get<IProductFiltersMetaAdmin>(
    'admin/products/filters_meta/'
  );
  return resp.data;
};

export const getStocksDetails = async (productId: string) => {
  const resp = await api.get<IStocksDetails>(
    `admin/products/${productId}/stocks/`
  );
  return resp.data;
};

export const toggleProductPublish = async (
  productId: string,
  data: unknown
) => {
  const resp = await api.patch<IProductAdmin>(
    `admin/products/${productId}/`,
    data
  );
  return resp.data;
};
