import { useMemo } from 'react';

import { PaginationQueryParams } from '../types/pagination/interfaces';

import useFetcher from './useFetcher';
import usePagination from './usePagination';
import useUrlParams, { UrlParamConfig } from './useUrlParams';

export interface UseFilterOptions<TFilters, TParams, TItem> {
  filterConfigs: UrlParamConfig<TFilters>[];
  defaultFilters?: Partial<TFilters>;
  fetcher: (params: TParams) => Promise<{ results: TItem[]; count: number }>;
  transformParams?: (
    filters: TFilters,
    limit: number,
    offset: number
  ) => TParams;
  deps?: unknown[];
  defaultLimit?: number;
}

export function useFilter<
  TFilters,
  TParams extends PaginationQueryParams,
  TItem,
>({
  filterConfigs,
  defaultFilters = {},
  fetcher,
  transformParams,
  deps,
  defaultLimit = 8,
}: UseFilterOptions<TFilters, TParams, TItem>) {
  const [filters, setFilters] = useUrlParams<TFilters>(
    filterConfigs,
    defaultFilters
  );
  const { page, limit, offset, setPage } = usePagination(defaultLimit);

  const params = useMemo(() => {
    if (transformParams)
      return { ...transformParams(filters, limit, offset), limit, offset };
    return { ...filters, limit, offset } as unknown as TParams;
  }, [filters, limit, offset, transformParams]);

  const additionalDeps = deps ? deps : [];

  const {
    items: data,
    count,
    isLoading,
    refresh,
    setItems: setData,
  } = useFetcher<TParams, TItem>({
    fetcher,
    params,
    deps: [
      ...filterConfigs.map(c => (filters as TFilters)[c.key]),
      ...additionalDeps,
      page,
    ],
  });

  const deleteFilter = (...keys: (keyof TFilters)[]) => {
    const clear: Partial<TFilters> = {};
    keys.forEach(k => {
      clear[k] = undefined;
    });
    setFilters(clear);
  };

  return {
    // Filters
    filters,
    setFilters,
    deleteFilter,
    // Pagination
    page,
    limit,
    setPage,
    // Data
    data,
    count,
    isLoading,
    refresh,
    setData,
  };
}
