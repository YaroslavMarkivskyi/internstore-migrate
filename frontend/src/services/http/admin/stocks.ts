import { ccApi as api } from '../api';

import {
  patchStockProduct,
  ProductsDistribution,
  Stock,
} from 'src/types/stocks/interfaces';

export const getStock = async (id: string): Promise<Stock> => {
  const resp = await api.get(`inventory/stocks/${id}`);
  return resp.data;
};

// Inventory's move endpoint moves one stock item to one destination per
// call -- MoveToStockMenu's UI lets an admin split a single product's
// quantity across several destination stocks in one save, so this fires
// one POST per transfer.
export const distributeProducts = async (
  payload: ProductsDistribution,
  sourceStockId: string,
  productEntryId: string
) => {
  await Promise.all(
    payload.transfers.map(transfer =>
      api.post(`inventory/stocks/${sourceStockId}/items/${productEntryId}/move`, {
        toStockId: transfer.targetStock,
        quantity: transfer.quantityToTransfer,
      })
    )
  );
};

export const getStocks = async (): Promise<Stock[]> => {
  // No trailing slash -- see stockService.ts's STOCKS_BASE_URL comment
  // (avoids a 307 redirect that drops the public Host header).
  const resp = await api.get('inventory/stocks');
  return resp.data;
};

interface StockTransfer {
  target_stock: string;
  quantity_to_transfer: number;
}

interface BulkAddStocksRequest {
  product_id: string;
  transfers: StockTransfer[];
}

// "Put in stock" -- reuses Inventory's add-or-increment receive_stock_item
// endpoint, one POST per destination stock (exactly what "put this product
// in these stocks with these quantities" means).
export const bulkAddStocks = async (data: BulkAddStocksRequest) => {
  await Promise.all(
    data.transfers.map(transfer =>
      api.post(`inventory/stocks/${transfer.target_stock}/items`, {
        productId: data.product_id,
        quantity: transfer.quantity_to_transfer,
      })
    )
  );
};

export const updateStockProduct = async (
  stockId: string,
  productEntryId: string,
  payload: patchStockProduct
) => {
  const resp = await api.patch(
    `inventory/stocks/${stockId}/items/${productEntryId}`,
    payload
  );
  return resp.data;
};
