import { toQueryParams } from '@utils/toQueryParams';

import { ccApi as api } from '../api';

import { PaginatedResults } from '../../../types/pagination/interfaces';
import {
  IStock,
  IStockProduct,
  IStockProductFilterParams,
} from '../../../types/stocks/interfaces';

const STOCKS_BASE_URL = 'admin/stocks/';

export const stockService = {
  getAllStocks: async (): Promise<IStock[]> => {
    const resp = await api.get(STOCKS_BASE_URL);
    return resp.data;
  },
  createStock: async (data: IStock): Promise<IStock> => {
    const resp = await api.post<IStock>(STOCKS_BASE_URL, data);
    return resp.data;
  },
  updateStock: async (stockId: number, data: IStock): Promise<IStock> => {
    const resp = await api.patch<IStock>(`${STOCKS_BASE_URL}${stockId}/`, data);
    return resp.data;
  },
  deleteStock: async (stockId: number): Promise<void> => {
    await api.delete(`${STOCKS_BASE_URL}${stockId}/`);
  },
  getProductsByStockId: async (
    stockId: number,
    filterParams: IStockProductFilterParams
  ): Promise<PaginatedResults<IStockProduct>> => {
    const queryParams = toQueryParams<IStockProductFilterParams>(filterParams);
    const resp = await api.get<PaginatedResults<IStockProduct>>(
      `${STOCKS_BASE_URL}${stockId}/products/${queryParams}`
    );
    return resp.data;
  },
  getProductsFromAllStocks: async (
    filterParams: IStockProductFilterParams
  ): Promise<PaginatedResults<IStockProduct>> => {
    const queryParams = toQueryParams<IStockProductFilterParams>(filterParams);
    const resp = await api.get<PaginatedResults<IStockProduct>>(
      `${STOCKS_BASE_URL}products/${queryParams}`
    );
    return resp.data;
  },
};
