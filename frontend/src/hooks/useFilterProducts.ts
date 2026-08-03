import { getProducts } from '@services/http/admin/products';

import {
  IProductAdmin,
  IProductFilterParamsAdmin,
} from '../types/products/interfaces';
import { ProductOrderingAdmin } from '../types/products/types';

import { useFilter } from './useFilter';
import { UrlParamConfig } from './useUrlParams';

const filterConfigs: UrlParamConfig<IProductFilterParamsAdmin>[] = [
  {
    key: 'category',
    parser: val => val.split(','),
    serializer: v => (Array.isArray(v) ? v.join(',') : String(v)),
  },
  { key: 'priceMin', parser: parseFloat },
  { key: 'search', parser: val => val },
  { key: 'priceMax', parser: parseFloat },
  { key: 'totalQuantityMin', parser: parseInt },
  { key: 'totalQuantityMax', parser: parseInt },
  { key: 'ordering', parser: val => val as ProductOrderingAdmin },
  { key: 'isPublished', parser: val => val === 'true' },
];

const useFilterProducts = (limit: number = 8) => {
  const {
    data: products,
    filters,
    ...rest
  } = useFilter<
    IProductFilterParamsAdmin,
    IProductFilterParamsAdmin,
    IProductAdmin
  >({
    filterConfigs: filterConfigs,
    fetcher: getProducts,
    defaultLimit: limit,
  });

  return {
    ...rest,
    ...filters,
    products,
  };
};
export default useFilterProducts;
