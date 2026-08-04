import { fetchCategories, fetchProducts } from '@services/http/catalog';

import { ccApi as api } from '../api';

import { PaginatedResults } from '../../../types/pagination/interfaces';
import {
  INormalizedProduct,
  IStock,
  IStockProduct,
  IStockProductFilterParams,
} from '../../../types/stocks/interfaces';

// No trailing slash: the backend route is registered as exactly "/stocks"
// (prefix="/stocks" + @router.get(""), see
// internstore-migrate/services/inventory/src/inventory/routers/stocks.py).
// Requesting "/stocks/" doesn't match, so Starlette's default
// redirect_slashes issues a 307 to "/stocks" built from the request's Host
// header — which nginx passes through as its own upstream target
// ("inventory:8000", nginx's default $proxy_host when no `proxy_set_header
// Host` is set) rather than the public origin. The browser then tries to
// follow that absolute http://inventory:8000/... URL directly, which of
// course it can't resolve/CORS-blocks. Keeping this slash-free avoids
// triggering the redirect in the first place.
const STOCKS_BASE_URL = 'inventory/stocks';

interface StockItemDetailRaw {
  id: string;
  stockId: string;
  productId: string;
  name: string;
  quantity: number;
  temperature: number | null;
  humidity: number | null;
}

// Inventory has no product name/price/category/image of its own -- every
// stock-item row is joined client-side with Catalog's product + category
// list, same client-side-composition pattern admin/products.ts already
// uses for the Admin Products list.
const fetchStockItemsDetailed = async (
  stockId?: string
): Promise<StockItemDetailRaw[]> => {
  const resp = await api.get<StockItemDetailRaw[]>('inventory/items/detailed', {
    params: stockId ? { stockId } : undefined,
  });
  return resp.data;
};

const toStockProducts = async (
  items: StockItemDetailRaw[],
  filterParams: IStockProductFilterParams
): Promise<PaginatedResults<IStockProduct>> => {
  const [rawProducts, categories] = await Promise.all([
    fetchProducts(),
    fetchCategories(),
  ]);
  const productById = new Map(rawProducts.map(product => [product.id, product]));

  let stockProducts: IStockProduct[] = items.flatMap(item => {
    const raw = productById.get(item.productId);
    if (!raw) return [];

    const category = categories.find(c => c.id === raw.categoryId);
    const normalized: INormalizedProduct = {
      id: raw.id,
      name: raw.name,
      price: raw.price,
      minTemperature: raw.minTemperature ?? 0,
      maxTemperature: raw.maxTemperature ?? 0,
      image: '',
      category: category?.name ?? '',
    };

    return [
      {
        id: item.id,
        stockId: item.stockId,
        quantity: item.quantity,
        product: normalized,
      },
    ];
  });

  if (filterParams.category?.length) {
    const categorySet = new Set(filterParams.category);
    stockProducts = stockProducts.filter(sp => {
      const raw = productById.get(sp.product.id);
      return raw && categorySet.has(raw.categoryId);
    });
  }
  if (filterParams.priceMin !== undefined) {
    stockProducts = stockProducts.filter(sp => sp.product.price >= filterParams.priceMin!);
  }
  if (filterParams.priceMax !== undefined) {
    stockProducts = stockProducts.filter(sp => sp.product.price <= filterParams.priceMax!);
  }

  const count = stockProducts.length;
  const offset = filterParams.offset ?? 0;
  const limit = filterParams.limit ?? count;
  return { count, results: stockProducts.slice(offset, offset + limit) };
};

export const stockService = {
  getAllStocks: async (): Promise<IStock[]> => {
    const resp = await api.get<IStock[]>(STOCKS_BASE_URL);
    return resp.data;
  },
  createStock: async (data: IStock): Promise<IStock> => {
    const resp = await api.post<IStock>(STOCKS_BASE_URL, data);
    return resp.data;
  },
  updateStock: async (stockId: string, data: IStock): Promise<IStock> => {
    const resp = await api.patch<IStock>(`${STOCKS_BASE_URL}/${stockId}`, data);
    return resp.data;
  },
  deleteStock: async (stockId: string): Promise<void> => {
    await api.delete(`${STOCKS_BASE_URL}/${stockId}`);
  },
  getProductsByStockId: async (
    stockId: string,
    filterParams: IStockProductFilterParams
  ): Promise<PaginatedResults<IStockProduct>> => {
    const items = await fetchStockItemsDetailed(stockId);
    return toStockProducts(items, filterParams);
  },
  getProductsFromAllStocks: async (
    filterParams: IStockProductFilterParams
  ): Promise<PaginatedResults<IStockProduct>> => {
    const items = await fetchStockItemsDetailed();
    return toStockProducts(items, filterParams);
  },
};
