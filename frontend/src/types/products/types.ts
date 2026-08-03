export type ProductOrderingPositive = 'price' | 'total_quantity';
export type ProductOrderingNegative = '-price' | '-total_quantity';
export type ProductOrderingAdmin =
  | ProductOrderingPositive
  | ProductOrderingNegative;

export type ProductOrderingPublic = 'price' | '-price';
