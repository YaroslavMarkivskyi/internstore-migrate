import { IStock } from 'src/types/stocks/interfaces';

// '' is the "All Stocks" sentinel (no stockId in the URL).
export const isValidStockId = (id: string, stocks: IStock[]) => {
  const validIds = ['', ...stocks.map(s => s.id)];
  return validIds.includes(id);
};
