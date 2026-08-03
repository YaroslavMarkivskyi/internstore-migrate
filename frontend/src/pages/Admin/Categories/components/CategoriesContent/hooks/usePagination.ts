import { useCallback, useState } from 'react';

export interface PaginationState {
  currentPage: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

export interface UsePaginationProps {
  initialPage?: number;
  initialPageSize?: number;
}

export interface UsePaginationReturn {
  // State
  pagination: PaginationState;

  // Computed properties
  startItem: number;
  endItem: number;
  isFirstPage: boolean;
  isLastPage: boolean;

  // Actions
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  setTotalItems: (total: number) => void;
  reset: () => void;

  // Utils
  getPaginationInfo: (format?: 'short' | 'full') => string;
}

/**
 * Custom hook for handling pagination state and calculations
 */
export const usePagination = ({
  initialPage = 1,
  initialPageSize = 8,
}: UsePaginationProps = {}): UsePaginationReturn => {
  const [pagination, setPagination] = useState<PaginationState>({
    currentPage: initialPage,
    pageSize: initialPageSize,
    totalItems: 0,
    totalPages: 0,
  });

  // Calculate derived values
  const startItem =
    pagination.totalItems === 0
      ? 0
      : (pagination.currentPage - 1) * pagination.pageSize + 1;

  const endItem = Math.min(
    pagination.currentPage * pagination.pageSize,
    pagination.totalItems
  );

  const isFirstPage = pagination.currentPage === 1;
  const isLastPage =
    pagination.currentPage === pagination.totalPages ||
    pagination.totalPages === 0;

  // Set current page
  const setPage = useCallback((page: number) => {
    setPagination(prev => ({
      ...prev,
      currentPage: Math.max(1, Math.min(page, prev.totalPages || 1)),
    }));
  }, []);

  // Set page size and recalculate total pages
  const setPageSize = useCallback((size: number) => {
    setPagination(prev => {
      const newTotalPages = Math.ceil(prev.totalItems / size) || 1;
      const newCurrentPage = Math.min(prev.currentPage, newTotalPages);

      return {
        ...prev,
        pageSize: size,
        totalPages: newTotalPages,
        currentPage: newCurrentPage,
      };
    });
  }, []);

  // Set total items and recalculate total pages
  const setTotalItems = useCallback((total: number) => {
    setPagination(prev => {
      const newTotalPages = Math.ceil(total / prev.pageSize) || 1;
      const newCurrentPage = Math.min(prev.currentPage, newTotalPages);

      return {
        ...prev,
        totalItems: total,
        totalPages: newTotalPages,
        currentPage: newCurrentPage,
      };
    });
  }, []);

  // Reset pagination state
  const reset = useCallback(() => {
    setPagination({
      currentPage: 1,
      pageSize: initialPageSize,
      totalItems: 0,
      totalPages: 0,
    });
  }, [initialPageSize]);

  // Get formatted pagination info text
  const getPaginationInfo = useCallback(
    (format: 'short' | 'full' = 'full') => {
      if (pagination.totalItems === 0) {
        return 'No items';
      }

      if (format === 'short') {
        return `${startItem}-${endItem} of ${pagination.totalItems}`;
      }

      return `Showing products ${startItem} - ${endItem} of ${pagination.totalItems}`;
    },
    [pagination.totalItems, startItem, endItem]
  );

  return {
    pagination,
    startItem,
    endItem,
    isFirstPage,
    isLastPage,
    setPage,
    setPageSize,
    setTotalItems,
    reset,
    getPaginationInfo,
  };
};
