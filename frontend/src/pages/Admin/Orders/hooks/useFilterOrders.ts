import dayjs from 'dayjs';

import { getOrders } from '@services/http/admin/orders';
import showToast from '@utils/showToast';

import { useFilter } from '../../../../hooks/useFilter';
import { UrlParamConfig } from '../../../../hooks/useUrlParams';
import {
  IOrderAdmin,
  IOrdersFilterParamsAdmin,
  IOrdersFilterParamsAdminRaw,
} from '../../../../types/orders/interfaces';
import {
  DateRange,
  OrderOrdering,
  OrderStatus,
} from '../../../../types/orders/types';

const isDateRangeArray = (value: unknown): value is DateRange[] => {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    typeof value[0] === 'object' &&
    'from' in value[0] &&
    'to' in value[0] &&
    dayjs.isDayjs(value[0].from) &&
    dayjs.isDayjs(value[0].to)
  );
};

const parseDateRange = (datesRaw: string) => {
  try {
    const dateListRaw = datesRaw.split(',');
    return dateListRaw.map(rangeRaw => {
      const rangeSplit = rangeRaw.split('|');
      const dateRange: DateRange = {
        from: dayjs(rangeSplit[0]),
        to: dayjs(rangeSplit[1]),
      };
      return dateRange;
    });
  } catch (error) {
    console.log(error);
    showToast({
      message: 'Error parsing date',
      type: 'error',
      autoClose: 2000,
    });
  }
  return [];
};

const serializeDateRange = (
  dates: IOrdersFilterParamsAdmin[keyof IOrdersFilterParamsAdmin]
) => {
  try {
    if (isDateRangeArray(dates)) {
      const rawDateRangesList = dates.map(
        range => `${range.from.toISOString()}|${range.to.toISOString()}`
      );
      return rawDateRangesList.join(',');
    }
  } catch (error) {
    console.log(error);
    showToast({
      message: 'Error serializing date',
      type: 'error',
      autoClose: 2000,
    });
  }
  return '';
};

const filterConfigs: UrlParamConfig<IOrdersFilterParamsAdmin>[] = [
  { key: 'ordering', parser: val => val as OrderOrdering },
  { key: 'archived', parser: val => val === 'true' },
  {
    key: 'status',
    parser: val => val.split(',') as OrderStatus[],
    serializer: v => (Array.isArray(v) ? v.join(',') : String(v)),
  },
  {
    key: 'date',
    parser: parseDateRange,
    serializer: serializeDateRange,
  },
];

const useFilterOrders = (limit: number = 8) => {
  const {
    data: orders,
    filters,
    ...rest
  } = useFilter<
    IOrdersFilterParamsAdmin,
    IOrdersFilterParamsAdminRaw,
    IOrderAdmin
  >({
    filterConfigs: filterConfigs,
    defaultFilters: {
      archived: false,
    },
    fetcher: getOrders,
    transformParams: filters => ({
      ...filters,
      date: filters.date ? serializeDateRange(filters.date) : undefined,
    }),
    defaultLimit: limit,
  });

  return {
    ...rest,
    ...filters,
    orders,
  };
};
export default useFilterOrders;
