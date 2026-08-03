import { ICategory } from '../categories/interfaces';
import { searchQueryParams } from '../search/interfaces';

import { ProductOrderingAdmin, ProductOrderingPublic } from './types';

// Catalog product ids are UUIDs on the backend, not numeric — see
// internstore-migrate/services/catalog/src/catalog/schemas.py.
export interface IProductShort {
  id: string;
  image?: string;
  name: string;
  category?: ICategory;
}

export interface IProductBase extends IProductShort {
  price: string;
  description: string;
  highlightedName?: string;
}

export interface IProductImage {
  id: string;
  image: string;
}

// **********************************
// *                                *
// *         Admin Types            *
// *                                *
// **********************************
export interface IProductAdmin extends IProductBase {
  minTemperature: number;
  maxTemperature: number;
  isPublished: boolean;
  totalQuantity: number;
}

export interface IProductFilterParamsAdmin extends searchQueryParams {
  priceMax?: number;
  priceMin?: number;
  totalQuantityMax?: number;
  totalQuantityMin?: number;
  ordering?: ProductOrderingAdmin;
  category?: string[];
  isPublished?: boolean;
}

export interface IProductFiltersMetaAdmin {
  maxPrice: string;
  minPrice: string;
  minQuantity: number;
  maxQuantity: number;
}

// **********************************
// *                                *
// *         Public Types           *
// *                                *
// **********************************
export interface IProductPublic extends IProductBase {
  inStock: boolean;
}

export interface IProductFilterParamsPublic extends searchQueryParams {
  ordering?: ProductOrderingPublic;
  category?: string[];
  priceMax?: number;
  priceMin?: number;
  ids?: string[];
}

export interface IProductFiltersMetaPublic {
  maxPrice: string;
  minPrice: string;
}
