import { useCallback, useState } from 'react';

import { getCategoryProducts } from '@services/http/admin/categories';
import {
  deleteProduct,
  updateProductCategory,
} from '@services/http/admin/products';
import showToast from '@utils/showToast';

import { Category, Product, ProductLoadState } from '../types';

import { usePagination } from './usePagination';

interface UseProductsProps {
  setProductLoadState: (categoryId: string, state: ProductLoadState) => void;
  updateCategoryInList: (
    categoryId: string,
    updater: (category: Category) => Category
  ) => void;
  initialPageSize?: number;
  categories: Category[];
}

interface UseProductsReturn {
  // State
  paginationState: ReturnType<typeof usePagination>;
  loadingState: { products: boolean };
  isMovingLastProduct: boolean;

  // Actions
  loadCategoryProducts: (
    category: Category,
    page?: number
  ) => Promise<Category | undefined>;
  handlePageChange: (category: Category, newPage: number) => void;
  handleMoveProducts: (
    sourceCategory: Category,
    productIds: string[],
    targetCategoryId: string
  ) => Promise<void>;
  handleDeleteProducts: (
    category: Category,
    productIds: string[]
  ) => Promise<void>;
  handleUpdateCategoryProducts: (
    categoryId: string,
    updatedProducts: Product[]
  ) => void;
}

/**
 * Hook for managing products within categories
 */
export const useProducts = ({
  setProductLoadState,
  updateCategoryInList,
  initialPageSize = 8,
  categories,
}: UseProductsProps): UseProductsReturn => {
  // Use the pagination hook
  const paginationState = usePagination({ initialPageSize });
  const { pagination, setPage, setTotalItems } = paginationState;

  // Loading state
  const [loadingState, setLoadingState] = useState({
    products: false,
  });

  // State to track if we're currently moving the last product
  const [isMovingLastProduct, setIsMovingLastProduct] = useState(false);

  // Memoized function to load products for a category
  const loadCategoryProducts = useCallback(
    async (category: Category, page: number = 1) => {
      if (!category) return;

      const categoryId = category.id;

      try {
        // Set loading state immediately to show spinner
        setLoadingState(prev => ({ ...prev, products: true }));

        // Update load state
        setProductLoadState(categoryId, ProductLoadState.Loading);

        // Always try to load products from the API
        try {
          const response = await getCategoryProducts(categoryId, page);

          // Process response data
          let productsData: Product[] = [];
          let responseCount = 0;

          if ('results' in response && Array.isArray(response.results)) {
            productsData = response.results as unknown as Product[];
            responseCount = response.count;

            // Update pagination information
            setTotalItems(responseCount);
            setPage(page);
          } else if (Array.isArray(response)) {
            productsData = response as unknown as Product[];
            responseCount = productsData.length;

            // Update pagination information
            setTotalItems(responseCount);
            setPage(page);
          }

          // Create updated category with products
          const updatedCategory = {
            ...category,
            products: productsData,
            productCount: responseCount, // Use the count from API response
          };

          // Update category
          updateCategoryInList(categoryId, () => updatedCategory);

          // Mark as loaded
          setProductLoadState(categoryId, ProductLoadState.Loaded);

          return updatedCategory;
        } catch {
          // If API call fails, handle empty state
          if (category.productCount === 0) {
            // Create empty category with products
            const updatedCategory = {
              ...category,
              products: [],
              productCount: 0,
            };

            // Update category
            updateCategoryInList(categoryId, () => updatedCategory);

            // Update pagination information for empty category
            setTotalItems(0);
            setPage(1);

            // Mark as loaded
            setProductLoadState(categoryId, ProductLoadState.Loaded);

            return updatedCategory;
          } else {
            // For non-empty categories, mark as error
            setProductLoadState(categoryId, ProductLoadState.Error);
            // Log error but don't throw to allow UI to handle gracefully
          }
        }
      } finally {
        setLoadingState(prev => ({ ...prev, products: false }));
      }
    },
    [setPage, setProductLoadState, setTotalItems, updateCategoryInList]
  );

  // Handle page change
  const handlePageChange = useCallback(
    (category: Category, newPage: number) => {
      if (category) {
        setPage(newPage);
        loadCategoryProducts(category, newPage);
      }
    },
    [loadCategoryProducts, setPage]
  );

  // Handle moving products between categories
  const handleMoveProducts = useCallback(
    async (
      sourceCategory: Category,
      productIds: string[],
      targetCategoryId: string
    ) => {
      try {
        if (!sourceCategory || !productIds.length) return;

        // Get current page and product count before updates
        const currentPageBeforeUpdate = pagination.currentPage;
        const oldTotalItems = pagination.totalItems;

        // Check if moving all products
        const isMovingAllProducts =
          sourceCategory.products &&
          productIds.length === sourceCategory.products.length;

        // Set loading states
        if (isMovingAllProducts) {
          setIsMovingLastProduct(true);
          setLoadingState(prev => ({ ...prev, products: true }));
        }

        // Store API calls to execute in parallel
        const apiPromises = [];

        // For each product being moved
        const productsToMove: Product[] = [];
        for (const productId of productIds) {
          // Find the product in the source category
          const productToMove = sourceCategory.products?.find(
            p => p.id === productId
          );

          if (!productToMove) continue;

          productsToMove.push(productToMove);

          // Queue the API update
          apiPromises.push(updateProductCategory(productId, targetCategoryId));
        }

        // Store how many products are being moved for later reference
        const numProductsToMove = productsToMove.length;

        // Find the target category
        const targetCategory = categories.find(c => c.id === targetCategoryId);
        if (!targetCategory) {
          // Target category not found, can't proceed
          return;
        }

        // Optimistically update target category's product count in the UI
        // This ensures the menu and header immediately show the updated count
        const updatedTargetCategory = {
          ...targetCategory,
          productCount: (targetCategory.productCount || 0) + numProductsToMove,
          // If the target category had no products before, we can optimistically set them
          products: targetCategory.products || [],
        };

        // Update the target category in our state
        updateCategoryInList(targetCategoryId, () => updatedTargetCategory);

        // Update the source category (remove products)
        const updatedSourceCategory = {
          ...sourceCategory,
          products:
            sourceCategory.products?.filter(p => !productIds.includes(p.id)) ||
            [],
          productCount: Math.max(
            0,
            (sourceCategory.productCount || 0) - numProductsToMove
          ),
        };

        updateCategoryInList(sourceCategory.id, () => updatedSourceCategory);

        // Calculate pagination changes for source category
        const newTotalItems = updatedSourceCategory.productCount;
        setTotalItems(newTotalItems);

        const newTotalPages = pagination.totalPages;
        const currentPageIsValid =
          pagination.currentPage <= newTotalPages ? pagination.currentPage : 1;

        // Determine if need to reload based on pagination threshold
        const paginationRemoved =
          oldTotalItems > pagination.pageSize &&
          newTotalItems <= pagination.pageSize;

        // Wait for API calls to complete
        await Promise.all(apiPromises);

        // Create a flag to track if we need to reload the source category
        const needToReloadSource =
          paginationRemoved ||
          currentPageIsValid !== currentPageBeforeUpdate ||
          isMovingAllProducts;

        // Set the target category load state to "not loaded"
        // This will force a reload when the category is selected
        setProductLoadState(targetCategoryId, ProductLoadState.NotLoaded);

        // Handle source category reloading if needed
        if (needToReloadSource) {
          // Use timeout to ensure UI updates first
          setTimeout(() => {
            loadCategoryProducts(
              updatedSourceCategory,
              currentPageIsValid
            ).finally(() => {
              setIsMovingLastProduct(false);
              setLoadingState(prev => ({ ...prev, products: false }));
            });
          }, 50);
        } else {
          // Clear flags if we didn't reload
          setIsMovingLastProduct(false);
          setLoadingState(prev => ({ ...prev, products: false }));
        }
      } catch {
        // Handle error
        showToast({
          message: 'An error occurred while moving products',
          type: 'error',
        });

        // Clear flags in case of error
        setIsMovingLastProduct(false);
        setLoadingState(prev => ({ ...prev, products: false }));
      }
    },
    [
      pagination,
      loadCategoryProducts,
      updateCategoryInList,
      setTotalItems,
      setProductLoadState,
      categories,
    ]
  );

  // Handle deletion of multiple products
  const handleDeleteProducts = useCallback(
    async (category: Category, productIds: string[]) => {
      if (!category || productIds.length === 0) return;

      try {
        setLoadingState(prev => ({ ...prev, products: true }));

        // Show appropriate loading message
        const productCount = productIds.length;
        if (productCount > 3) {
          // Show a message for bulk deletion
          showToast({
            message: `Deleting ${productCount} products. This may take a moment...`,
            autoClose: 3000,
            type: 'info',
          });
        }

        // Track successful and failed deletions
        const results = {
          successful: 0,
          failed: 0,
          failedIds: [] as string[],
        };

        // Delete products one by one - this could potentially be optimized with a batch operation
        for (const productId of productIds) {
          try {
            await deleteProduct(productId);
            results.successful++;
          } catch {
            results.failed++;
            results.failedIds.push(productId);

            // Only show individual failures if we're not in a bulk operation
            if (productCount <= 3) {
              showToast({
                message: `Failed to delete product ${productId}`,
                type: 'error',
              });
            }
          }
        }

        // Show summary of results
        if (results.successful > 0 && results.failed === 0) {
          showToast({
            message: `Successfully deleted ${results.successful} product${results.successful > 1 ? 's' : ''}`,
            type: 'success',
          });
        } else if (results.successful > 0 && results.failed > 0) {
          showToast({
            message: `Deleted ${results.successful} products, but failed to delete ${results.failed} products.`,
            type: 'warning',
          });
        } else if (results.successful === 0 && results.failed > 0) {
          showToast({
            message: `Failed to delete any products. Please try again.`,
            type: 'success',
          });
        }

        // Update the category's product count and products array
        if (results.successful > 0) {
          // Calculate the new total items after deletion
          const newTotalItems = Math.max(
            0,
            (category.productCount || 0) - results.successful
          );

          // Update the total items in pagination
          setTotalItems(newTotalItems);

          // Check if all products are deleted
          const allProductsDeleted = newTotalItems === 0;

          // Create updated category
          const updatedCategory = {
            ...category,
            productCount: newTotalItems,
            products: allProductsDeleted
              ? []
              : category.products?.filter(
                  p =>
                    !productIds.includes(p.id) ||
                    results.failedIds.includes(p.id)
                ),
          };

          // Update category in list
          updateCategoryInList(category.id, () => updatedCategory);

          // Check if current page is still valid
          const exactlyAtThreshold = newTotalItems === pagination.pageSize;

          // If page is now empty but there are still products, go to previous page
          let newCurrentPage = pagination.currentPage;
          if (
            newCurrentPage > pagination.totalPages &&
            pagination.totalPages > 0
          ) {
            newCurrentPage = pagination.totalPages;
          }

          // If at exactly threshold, reset to page 1
          if (exactlyAtThreshold) {
            newCurrentPage = 1;
          }

          // If all products deleted, no need for API call
          if (allProductsDeleted) {
            setLoadingState(prev => ({ ...prev, products: false }));
            setProductLoadState(category.id, ProductLoadState.Loaded);
            setPage(1);
          } else {
            // Reload the category with potentially updated page
            loadCategoryProducts(
              updatedCategory,
              exactlyAtThreshold ? 1 : newCurrentPage
            );
          }
        }
      } catch {
        // Handle error
        showToast({
          message: 'An error occurred while deleting products',
          type: 'error',
        });
      } finally {
        setLoadingState(prev => ({ ...prev, products: false }));
      }
    },
    [
      loadCategoryProducts,
      pagination.pageSize,
      pagination.currentPage,
      pagination.totalPages,
      setPage,
      setTotalItems,
      setProductLoadState,
      updateCategoryInList,
    ]
  );

  // Handle updating product publish status
  const handleUpdateCategoryProducts = useCallback(
    (categoryId: string, updatedProducts: Product[]) => {
      updateCategoryInList(categoryId, category => ({
        ...category,
        products: updatedProducts,
      }));
    },
    [updateCategoryInList]
  );

  return {
    // State
    paginationState,
    loadingState,
    isMovingLastProduct,

    // Actions
    loadCategoryProducts,
    handlePageChange,
    handleMoveProducts,
    handleDeleteProducts,
    handleUpdateCategoryProducts,
  };
};
