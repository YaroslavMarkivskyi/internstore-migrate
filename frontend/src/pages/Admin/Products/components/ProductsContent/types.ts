export interface Product {
  id: number;
  name: string;
  category: string;
  price: string;
  quantity: number;
  published: boolean;
  image: string;
}

export interface FilterState {
  categoryFilter: string[];
  publishFilter: string[];
  priceRange: [number, number];
  quantityRange: [number, number];
}

export interface SelectOption {
  value: string;
  label: string;
  endComponent?: React.ReactNode;
}
