import { useCallback } from 'react';

import { useSearchParams } from 'react-router-dom';

const usePagination = (defaultLimit: number = 8) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = parseInt(searchParams.get('page') || '1', 10);
  const limit = defaultLimit;
  const offset = (page - 1) * limit;

  const setPage = useCallback(
    (newPage: number) => {
      const params = new URLSearchParams(searchParams.toString());
      if (newPage === 1) {
        params.delete('page');
      } else {
        params.set('page', String(newPage));
      }
      setSearchParams(params);
    },
    [searchParams, setSearchParams]
  );

  return { page, limit, offset, setPage };
};

export default usePagination;
