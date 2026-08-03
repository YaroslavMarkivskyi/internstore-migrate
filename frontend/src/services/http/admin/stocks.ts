import { ccApi as api } from '../api';

import {
  patchStockProduct,
  ProductsDistribution,
  Stock,
} from 'src/types/stocks/interfaces';

// Inventory (services/inventory) only has GET/POST /stocks and
// GET/POST /stocks/{id}/items — none of the shapes this admin UI needs
// (distribute, product-bulk-add, products-list) exist on the backend yet.
// Left as-is; every call here will 404.

export const getStock = async (id: number): Promise<Stock> => {
  const resp = await api.get(`admin/stocks/${id}/`);
  return resp.data;
};

export const distributeProducts = async (
  payload: ProductsDistribution,
  sourceStockId: number,
  productEntryId: number
) => {
  const resp = await api.post(
    `admin/stocks/${sourceStockId}/list-products/${productEntryId}/distribute/`,
    payload
  );

  return resp.data;
};

export const getStocks = async (): Promise<Stock[]> => {
  const resp = await api.get('admin/stocks/');
  return resp.data;
};

interface StockTransfer {
  target_stock: number;
  quantity_to_transfer: number;
}

interface BulkAddStocksRequest {
  product_id: number;
  transfers: StockTransfer[];
}

export const bulkAddStocks = async (data: BulkAddStocksRequest) => {
  const resp = await api.post('admin/stocks/product-bulk-add/', data);
  return resp.data;
};

export const updateStockProduct = async (
  stockId: number,
  productEntryId: number,
  payload: patchStockProduct
) => {
  const resp = await api.patch(
    `/admin/stocks/${stockId}/products-list/${productEntryId}/`,
    payload
  );
  return resp.data;
};
