import { z } from 'zod';

import { ICategory } from '../categories/interfaces';
import { PaginationQueryParams } from '../pagination/interfaces';

import { stockSchema } from '../../schemas/stocks';

export interface ProductData {
  id: number;
  image: string;
  name: string;
  category: string;
  price: number;
  minTemperature: number;
  maxTemperature: number;
}

export interface ProductStockData {
  id: number;
  product: ProductData;
  quantity: number;
}

export interface Stock {
  id: number;
  name: string;
}

export interface ProductsDistribution {
  transfers: TransferUnit[];
}

export interface TransferUnit {
  targetStock: number;
  quantityToTransfer: number;
}

export type IStock = z.infer<typeof stockSchema>;

interface BaseProduct {
  id: number;
  name: string;
  price: number;
  minTemperature: number;
  maxTemperature: number;
  image: string;
}

export interface IProductWithCategory extends BaseProduct {
  category: ICategory;
  totalQuantity: number;
}

export interface INormalizedProduct extends BaseProduct {
  category: string;
}

export interface IStockProduct<TProduct = INormalizedProduct> {
  id?: number;
  product: TProduct;
  quantity: number;
  stockId: number;
}

export interface IStockProductFilterParams extends PaginationQueryParams {
  priceMax?: number;
  priceMin?: number;
  category?: number[];
}

export interface patchStockProduct {
  quantity?: number;
}

export interface IStockDetails {
  id: number;
  stockId: number;
  name: string;
  quantity: number;
  temperature: number;
  humidity: number;
}

export interface IStocksDetails {
  stocks: IStockDetails[];
}
