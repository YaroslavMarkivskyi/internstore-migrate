import { UrlParamConfig } from 'src/hooks/useUrlParams';

import { getOrders } from '@services/http/public/orders';

import { useFilter } from '../../../../hooks/useFilter';
import { IOrderPublic } from '../../../../types/orders/interfaces';
import { PaginationQueryParams } from '../../../../types/pagination/interfaces';

const filterConfigs: UrlParamConfig<PaginationQueryParams>[] = [];

const useOrders = (limit: number) => {
  const {
    data: orders,
    filters,
    ...rest
  } = useFilter<PaginationQueryParams, PaginationQueryParams, IOrderPublic>({
    filterConfigs: filterConfigs,
    fetcher: getOrders,
    defaultLimit: limit,
  });

  return {
    ...rest,
    ...filters,
    orders,
  };
};
export default useOrders;
