import { useParams } from 'react-router';

import { stockService } from '@services/http';

import { useFilter } from '../../../../hooks/useFilter';
import { UrlParamConfig } from '../../../../hooks/useUrlParams';
import {
  IStockProduct,
  IStockProductFilterParams,
} from '../../../../types/stocks/interfaces';

const filterConfigs: UrlParamConfig<IStockProductFilterParams>[] = [
  {
    key: 'category',
    parser: val => val.split(','),
    serializer: v => (Array.isArray(v) ? v.join(',') : String(v)),
  },
  { key: 'priceMin', parser: parseFloat },
  { key: 'priceMax', parser: parseFloat },
];

const useFilterStockProducts = (limit: number = 8) => {
  const { stockId } = useParams<{ stockId: string }>();
  const selectedStock = stockId ?? '';

  const {
    data: stockProducts,
    filters,
    ...rest
  } = useFilter<
    IStockProductFilterParams,
    IStockProductFilterParams,
    IStockProduct
  >({
    filterConfigs: filterConfigs,
    fetcher: fetchStockProducts,
    defaultLimit: limit,
    deps: [selectedStock],
  });

  async function fetchStockProducts(params: IStockProductFilterParams) {
    return selectedStock
      ? await stockService.getProductsByStockId(selectedStock, params)
      : await stockService.getProductsFromAllStocks(params);
  }

  return {
    ...rest,
    ...filters,
    stockProducts,
  };
};
export default useFilterStockProducts;
