export interface Temperature {
  store: string;
  temp: number;
}

export interface StatsDataType {
  salesThisWeek: number;
  newOrders: number;
  pendingPayment: number;
  paidOrders: number;
  valueThisWeek: string;
  cancelledOrders: number;
  rejectedOrders: number;
  temperatures: Temperature[];
}

export const statsData: StatsDataType = {
  salesThisWeek: 4,
  newOrders: 5,
  pendingPayment: 2,
  paidOrders: 5,
  valueThisWeek: '$1 000',
  cancelledOrders: 7,
  rejectedOrders: 10,
  temperatures: [
    { store: 'Store 1', temp: -7 },
    { store: 'Store 2', temp: -7 },
    { store: 'Store 3', temp: -7 },
  ],
};
