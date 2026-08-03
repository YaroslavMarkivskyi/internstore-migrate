import { PaginationQueryParams } from '../pagination/interfaces';

export interface FoundProduct {
  /** Title of product */
  id: string;
  name: string;
  highlightedName?: string;
  /** Source of image. */
  imageSrc: string;
  /** Action to be called when product is clicked */
  onClick: () => void;
}

export interface searchQueryParams extends PaginationQueryParams {
  highlightMatches?: boolean;
  search?: string;
}

export interface IHistoryItem {
  /** Action to be called when historyItem clicked */
  onClick?: () => void;
  /** Action to be called when historyItem delete button clicked */
  onDelete: () => void;
  /** Text of searched query */
  name: string;
}

export interface SearchHistoryItem {
  query: string;
}

export interface SearchHistoryActionPayload extends SearchHistoryItem {
  area: 'admin' | 'customer';
}

export interface SearchHistoryState {
  admin: SearchHistoryItem[];
  customer: SearchHistoryItem[];
}
