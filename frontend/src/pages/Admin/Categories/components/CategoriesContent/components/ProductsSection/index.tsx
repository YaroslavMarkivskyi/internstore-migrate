import { memo, useCallback } from 'react';

import { Box } from '@mui/material';

import { UsePaginationReturn } from '../../hooks/usePagination';
import { Category, Product, ProductLoadState } from '../../types';

import CategoryProducts from './components/CategoryProducts';

interface ProductsSectionProps {
  selectedCategory: Category | null;
  allCategories: Category[];
  loading: boolean;
  isUpdating: boolean;
  paginationState: UsePaginationReturn;
  onCategoryDeleted: (
    categoryId: string,
    options?: {
      deletionMode?: 'move' | 'unpublish_and_delete';
      targetCategoryId?: string;
    }
  ) => Promise<void>;
  onCategoryUpdated: (category: Category) => void;
  onProductsMove: (
    productIds: string[],
    targetCategoryId: string
  ) => Promise<void>;
  onProductsDelete: (productIds: string[]) => Promise<void>;
  onPageChange: (page: number) => void;
  setCategories: (products: Product[]) => void;
  setProductLoadState?: (categoryId: string, state: ProductLoadState) => void;
  onCategorySelect?: (category: Category) => void;
}

/**
 * Component that handles the products section display
 */
export const ProductsSection = memo(
  ({
    selectedCategory,
    allCategories,
    loading,
    isUpdating,
    paginationState,
    onCategoryDeleted,
    onCategoryUpdated,
    onProductsMove,
    onProductsDelete,
    onPageChange,
    setCategories,
    setProductLoadState,
    onCategorySelect,
  }: ProductsSectionProps) => {
    const { pagination } = paginationState;

    // Adapter functions to handle prop signature mismatches
    const handleCategoryUpdate = useCallback(
      (_categoryId: string, updatedCategory: Category) => {
        onCategoryUpdated(updatedCategory);
      },
      [onCategoryUpdated]
    );

    const handleSetCategories = useCallback(
      (_categoryId: string, updatedProducts: Product[]) => {
        setCategories(updatedProducts);
      },
      [setCategories]
    );

    return (
      <Box flex={1}>
        {selectedCategory ? (
          <CategoryProducts
            category={selectedCategory}
            allCategories={allCategories}
            loading={loading}
            isUpdating={isUpdating}
            onCategoryDeleted={onCategoryDeleted}
            onCategoryUpdated={handleCategoryUpdate}
            onProductsMove={onProductsMove}
            onProductsDelete={onProductsDelete}
            pagination={{
              currentPage: pagination.currentPage,
              totalPages: pagination.totalPages,
              totalItems: pagination.totalItems,
              pageSize: pagination.pageSize,
            }}
            onPageChange={onPageChange}
            setCategories={handleSetCategories}
            paginationInfo={paginationState.getPaginationInfo()}
            setProductLoadState={setProductLoadState}
            onCategorySelect={onCategorySelect}
          />
        ) : (
          <Box
            sx={{
              height: '400px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '4px',
              border: '1px solid #e0e0e0',
              bgcolor: '#f9f9f9',
            }}
          >
            Please select a category to view products
          </Box>
        )}
      </Box>
    );
  }
);
