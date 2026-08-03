import { useEffect, useState } from 'react';

import showToast from '@utils/showToast';

import { PaginationQueryParams } from '../types/pagination/interfaces';

export interface UseFetcherOptions<
  TParams extends PaginationQueryParams,
  TItem,
> {
  fetcher: (params: TParams) => Promise<{ results: TItem[]; count: number }>;
  params: TParams;
  deps?: unknown[];
}

const useFetcher = <TParams extends PaginationQueryParams, TItem>({
  fetcher,
  params,
  deps = [],
}: UseFetcherOptions<TParams, TItem>) => {
  const [items, setItems] = useState<TItem[]>([]);
  const [count, setCount] = useState(0);
  const [isLoading, setLoading] = useState(false);

  const fetch = async () => {
    if (!params.limit) return;

    setLoading(true);
    try {
      const data = await fetcher(params);
      setItems(data.results);
      setCount(data.count);
    } catch {
      showToast({
        message: 'Error fetching data',
        type: 'error',
      });
    }
    setLoading(false);
  };

  useEffect(() => {
    void fetch();
  }, deps);

  return { items, count, isLoading, refresh: fetch, setItems };
};

export default useFetcher;
