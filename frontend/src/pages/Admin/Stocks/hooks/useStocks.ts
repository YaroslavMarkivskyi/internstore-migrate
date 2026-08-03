import { useEffect, useState } from 'react';

import { stockService } from '@services/http';
import showToast from '@utils/showToast';

import { IStock } from 'src/types/stocks/interfaces';

export const useStocks = () => {
  const [stocks, setStocks] = useState<IStock[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchStocks = async () => {
    try {
      const data = await stockService.getAllStocks();
      setStocks(data);
    } catch {
      showToast({
        message: 'Failed to fetch stocks.',
        type: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStocks();
  }, []);

  return { stocks, loading, refetch: fetchStocks };
};
