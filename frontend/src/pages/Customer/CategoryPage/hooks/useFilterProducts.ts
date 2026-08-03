import { UrlParamConfig } from 'src/hooks/useUrlParams';

import { getProducts } from '@services/http/public/products';

import { useFilter } from '../../../../hooks/useFilter';
import {
  IProductFilterParamsPublic,
  IProductPublic,
} from '../../../../types/products/interfaces';
import { ProductOrderingPublic } from '../../../../types/products/types';

const filterConfigs: UrlParamConfig<IProductFilterParamsPublic>[] = [
  { key: 'priceMin', parser: parseFloat },
  { key: 'priceMax', parser: parseFloat },
  { key: 'search', parser: val => val },
  { key: 'ordering', parser: val => val as ProductOrderingPublic },
];

const useFilterProducts = (limit: number, category: string) => {
  const {
    data: products,
    filters,
    ...rest
  } = useFilter<
    IProductFilterParamsPublic,
    IProductFilterParamsPublic,
    IProductPublic
  >({
    filterConfigs: filterConfigs,
    fetcher: params => getProducts({ ...params, category: [category] }),
    defaultLimit: limit,
    deps: [category, limit],
  });

  return {
    ...rest,
    ...filters,
    products,
  };
};
export default useFilterProducts;
