// Catalog category ids are Postgres UUIDs on the backend, not
// numeric — see internstore-migrate/services/catalog/src/catalog/schemas.py.
export interface ICategory {
  id: string;
  name: string;
}

export interface ICategoryState {
  categories: Record<string, string>;
}

export interface ICategoryPreview extends ICategory {
  image: string | null;
}
