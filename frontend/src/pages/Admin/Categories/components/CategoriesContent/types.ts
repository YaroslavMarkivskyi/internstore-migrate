export interface Product {
  id: string;
  name: string;
  image: string;
  price: string;
  totalQuantity: number;
  isPublished: boolean;
  dragId?: string; // Used for drag operations
}

export interface Category {
  id: string;
  name: string;
  productCount: number;
  products?: Product[];
}

// API response type for new categories
export interface CategoryApiResponse extends Omit<Category, 'productCount'> {
  productCount?: number;
  product_count?: number;
}

export enum ProductLoadState {
  NotLoaded = 'not_loaded',
  Loading = 'loading',
  Loaded = 'loaded',
  Error = 'error',
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type CategoryProductsResponse = PaginatedResponse<Product> | Product[];
export type CategoriesResponse = PaginatedResponse<Category> | Category[];
