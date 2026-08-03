import { IStock } from 'src/types/stocks/interfaces';

export const isValidStockId = (id: number, stocks: IStock[]) => {
  const validIds = [0, ...stocks.map(s => s.id)];
  return validIds.includes(id);
};
