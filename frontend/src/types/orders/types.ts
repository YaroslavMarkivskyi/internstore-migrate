import { Dayjs } from 'dayjs';

export type OrderStatus =
  | 'new'
  | 'pending'
  | 'paid'
  | 'cancelled'
  | 'rejected'
  | 'done';

export type OrderProductOrderingPositive = 'price' | 'quantity' | 'total_price';
export type OrderProductOrderingNegative =
  | '-price'
  | '-quantity'
  | '-total_price';
export type OrderProductOrdering =
  | OrderProductOrderingPositive
  | OrderProductOrderingNegative;

export type OrderOrderingPositive = 'id' | 'created_at';
export type OrderOrderingNegative = '-id' | '-created_at';
export type OrderOrdering = OrderOrderingPositive | OrderOrderingNegative;

export type DateRange = { from: Dayjs; to: Dayjs };
