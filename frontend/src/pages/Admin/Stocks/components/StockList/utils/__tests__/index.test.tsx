import { isValidStockId } from '../validateSelectedStock';
import { IStock } from 'src/types/stocks/interfaces';

describe('isValidStockId', () => {
  const mockStocks: IStock[] = [
    { id: 1, name: 'Apple' },
    { id: 2, name: 'Tesla' },
    { id: 3, name: 'Amazon' },
  ];

  it('should return true for valid stock id', () => {
    expect(isValidStockId(0, mockStocks)).toBe(true);
    expect(isValidStockId(1, mockStocks)).toBe(true);
    expect(isValidStockId(2, mockStocks)).toBe(true);
    expect(isValidStockId(3, mockStocks)).toBe(true);
  });

  it('should return false for invalid stock id', () => {
    expect(isValidStockId(4, mockStocks)).toBe(false);
    expect(isValidStockId(-1, mockStocks)).toBe(false);
  });

  it('should return false if no stocks are provided', () => {
    const emptyStocks: IStock[] = [];
    expect(isValidStockId(1, emptyStocks)).toBe(false);
    expect(isValidStockId(0, emptyStocks)).toBe(true);
  });
});
