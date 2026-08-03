import { useCallback, useEffect, useState } from 'react';

import { useNavigate, useParams } from 'react-router-dom';

import axios from 'axios';

import {
  deleteCategory,
  getCategoriesWithProductCounts,
} from '@services/http/admin/categories';
import showToast from '@utils/showToast';

import { Category, CategoryApiResponse, ProductLoadState } from '../types';

interface UseCategoriesProps {
  onCategorySelected?: (category: Category) => void;
}

interface UseCategoriesReturn {
  // State
  categories: Category[];
  selectedCategory: Category | null;
  loadingState: { initial: boolean; categories: boolean };
  productLoadStates: Record<string, ProductLoadState>;

  // Actions
  handleCategorySelect: (category: Category) => void;
  handleCategoryAdded: (newCategory: CategoryApiResponse) => void;
  handleCategoryDeleted: (
    categoryId: string,
    options?: {
      deletionMode?: 'move' | 'unpublish_and_delete';
      targetCategoryId?: string;
    }
  ) => Promise<void>;
  handleCategoryUpdated: (
    categoryId: string,
    updatedCategory: Category
  ) => void;
  updateSelectedCategory: (updatedCategory: Category) => void;
  updateCategoryInList: (
    categoryId: string,
    updater: (category: Category) => Category
  ) => void;
  setProductLoadState: (categoryId: string, state: ProductLoadState) => void;
}

/**
 * Hook for managing categories in the admin panel
 */
export const useCategories = ({
  onCategorySelected,
}: UseCategoriesProps = {}): UseCategoriesReturn => {
  const { categoryId } = useParams<{ categoryId: string }>();
  const navigate = useNavigate();

  // State for categories management
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<Category | null>(
    null
  );
  const [productLoadStates, setProductLoadStates] = useState<
    Record<string, ProductLoadState>
  >({});
  const [loadingState, setLoadingState] = useState({
    initial: true,
    categories: true,
  });

  // Fetch all categories only once on component mount
  useEffect(() => {
    const loadCategories = async () => {
      try {
        setLoadingState(prev => ({ ...prev, categories: true }));
        const categoriesData = await getCategoriesWithProductCounts();

        // Initialize categories with empty products arrays and ensure productCount
        const processedCategories = categoriesData.map(
          (category: CategoryApiResponse) => {
            const { productCount, product_count, ...rest } = category;
            return {
              ...rest,
              productCount: productCount ?? product_count ?? 0,
              products: [], // Initialize with empty products array
            };
          }
        );

        // Initialize product load states for all categories
        const initialLoadStates: Record<string, ProductLoadState> = {};
        processedCategories.forEach((category: Category) => {
          initialLoadStates[category.id] = ProductLoadState.NotLoaded;
        });
        setProductLoadStates(initialLoadStates);

        setCategories(processedCategories);

        // Handle URL parameters
        if (categoryId && processedCategories.length > 0) {
          // Try to find the category matching the ID in the URL
          const categoryFromUrl = processedCategories.find(
            (c: Category) => c.id === categoryId
          );

          if (categoryFromUrl) {
            setSelectedCategory(categoryFromUrl);

            // Mark this category as needing product loading in the next effect cycle
            setProductLoadStates(prev => ({
              ...prev,
              [categoryFromUrl.id]: ProductLoadState.NotLoaded,
            }));

            // Notify parent component about category selection
            onCategorySelected?.(categoryFromUrl);
          } else {
            // If category ID in URL doesn't exist, redirect to first category
            if (processedCategories.length > 0) {
              navigate(`/admin/categories/${processedCategories[0].id}`, {
                replace: true,
              });
            }
          }
        } else if (processedCategories.length > 0) {
          // If no category ID in URL, navigate to the first category
          navigate(`/admin/categories/${processedCategories[0].id}`, {
            replace: true,
          });
        }
      } catch {
        // Error handling is done below
      } finally {
        setLoadingState(prev => ({ ...prev, categories: false }));
      }
    };

    if (loadingState.initial) {
      loadCategories();
      // Set initial to false after first load
      setLoadingState(prev => ({ ...prev, initial: false }));
    }
  }, [loadingState.initial, navigate, categoryId, onCategorySelected]);

  // Category selection handler
  const handleCategorySelect = useCallback(
    (category: Category) => {
      if (!selectedCategory || selectedCategory.id !== category.id) {
        // First, update the load state to ensure we reload products
        // This is important when moving products between categories
        setProductLoadStates(prev => ({
          ...prev,
          [category.id]: ProductLoadState.NotLoaded,
        }));

        // Update URL and selected category for immediate UI feedback
        navigate(`/admin/categories/${category.id}`);
        setSelectedCategory(category);

        // Notify parent component
        onCategorySelected?.(category);
      }
    },
    [navigate, selectedCategory, onCategorySelected, setProductLoadStates]
  );

  // Handler for when a new category is added
  const handleCategoryAdded = useCallback(
    (newCategory: CategoryApiResponse) => {
      // Transform API response to include productCount
      const { productCount, product_count, ...rest } = newCategory;

      // Process the new category to ensure it follows the same format as others
      const processedCategory = {
        ...rest,
        productCount: productCount ?? product_count ?? 0,
        products: [], // Initialize with empty products array
      };

      // Add the new category to the existing categories array
      setCategories(prevCategories => [...prevCategories, processedCategory]);

      // Initialize product load state for the new category
      setProductLoadStates(prev => ({
        ...prev,
        [processedCategory.id]: ProductLoadState.NotLoaded,
      }));

      // Select the newly added category and update URL
      navigate(`/admin/categories/${processedCategory.id}`);
      setSelectedCategory(processedCategory);

      // Notify parent component
      onCategorySelected?.(processedCategory);
    },
    [navigate, onCategorySelected]
  );

  // Handler for deleting a category
  const handleCategoryDeleted = useCallback(
    async (
      categoryId: string,
      options?: {
        deletionMode?: 'move' | 'unpublish_and_delete';
        targetCategoryId?: string;
      }
    ) => {
      try {
        // Call the API to delete the category with optional parameters
        await deleteCategory(categoryId, options);

        // Find the next category to select before removing the current one
        let nextSelectedCategory = null;

        if (selectedCategory && selectedCategory.id === categoryId) {
          // If products are being moved to a target category, select that one instead
          if (options?.deletionMode === 'move' && options?.targetCategoryId) {
            // Find the target category by ID
            const targetCategory = categories.find(
              c => c.id === options.targetCategoryId
            );
            if (targetCategory) {
              nextSelectedCategory = targetCategory;
            }
          }

          // If no target category was provided or found, fall back to the first category
          if (!nextSelectedCategory) {
            const remainingCategories = categories.filter(
              c => c.id !== categoryId
            );
            if (remainingCategories.length > 0) {
              nextSelectedCategory = remainingCategories[0];
            }
          }

          // Navigate to the next category
          if (nextSelectedCategory) {
            navigate(`/admin/categories/${nextSelectedCategory.id}`, {
              replace: true,
            });
          } else {
            // If no categories remain, navigate to the base categories route
            navigate('/admin/categories', { replace: true });
          }
        }

        // Remove the deleted category from the state
        setCategories(prevCategories =>
          prevCategories.filter(c => c.id !== categoryId)
        );

        // Update selected category if needed
        if (selectedCategory && selectedCategory.id === categoryId) {
          setSelectedCategory(nextSelectedCategory);

          // Notify parent component
          if (nextSelectedCategory) {
            onCategorySelected?.(nextSelectedCategory);
          }
        }
      } catch (error: unknown) {
        // Check for ProtectedError due to products referencing the category
        if (axios.isAxiosError(error) && error.response) {
          const errorData = error.response.data;
          const errorMessage =
            errorData?.detail || errorData?.message || errorData?.error || '';

          if (
            errorMessage.includes('ProtectedError') ||
            errorMessage.includes('protected foreign keys') ||
            errorMessage.includes('referenced through') ||
            (error.response.status === 500 &&
              errorMessage.includes('Product.category'))
          ) {
            // This is a protected foreign key error - products are referencing the category
            showToast({
              message:
                'Cannot delete this category because it contains products. Please move or delete all products first.',
              type: 'error',
              autoClose: 7000,
            });
          } else if (errorData?.error) {
            // Generic error with a message from the API
            showToast({
              message: errorData.error,
              type: 'error',
              autoClose: 5000,
            });
          } else {
            // Generic error without specific message
            showToast({
              message: 'Failed to delete category. Please try again later.',
              type: 'error',
            });
          }
        } else {
          // Non-axios errors
          showToast({
            message: 'Failed to delete category. Please try again later.',
            type: 'error',
          });
        }

        throw error; // Re-throw to allow caller to handle if needed
      }
    },
    [categories, navigate, onCategorySelected, selectedCategory]
  );

  // Handler for updating a category
  const handleCategoryUpdated = useCallback(
    (categoryId: string, updatedCategory: Category) => {
      // Update the categories list with the updated category
      setCategories(prevCategories =>
        prevCategories.map(category =>
          category.id === categoryId
            ? {
                ...category,
                name: updatedCategory.name,
                // Also update the product count if it's provided in updatedCategory
                ...(updatedCategory.productCount !== undefined && {
                  productCount: updatedCategory.productCount,
                }),
              }
            : category
        )
      );

      // If the updated category is currently selected, update it
      if (selectedCategory && selectedCategory.id === categoryId) {
        const newSelected = {
          ...selectedCategory,
          name: updatedCategory.name,
          // Also update the product count if it's provided
          ...(updatedCategory.productCount !== undefined && {
            productCount: updatedCategory.productCount,
          }),
        };
        setSelectedCategory(newSelected);

        // Notify parent component
        onCategorySelected?.(newSelected);
      }
    },
    [selectedCategory, onCategorySelected]
  );

  // Utility to update the selected category
  const updateSelectedCategory = useCallback(
    (updatedCategory: Category) => {
      setSelectedCategory(updatedCategory);

      // Also update in the categories list
      setCategories(prev =>
        prev.map(c => (c.id === updatedCategory.id ? updatedCategory : c))
      );

      // Notify parent component
      onCategorySelected?.(updatedCategory);
    },
    [onCategorySelected]
  );

  // Utility to update a category in the list
  const updateCategoryInList = useCallback(
    (categoryId: string, updater: (category: Category) => Category) => {
      setCategories(prev => {
        return prev.map(c => {
          if (c.id === categoryId) {
            const updated = updater(c);
            return updated;
          }
          return c;
        });
      });

      // Also update selected category if needed
      if (selectedCategory && selectedCategory.id === categoryId) {
        const updated = updater(selectedCategory);
        setSelectedCategory(updated);

        // Notify parent component
        onCategorySelected?.(updated);
      }
    },
    [selectedCategory, onCategorySelected]
  );

  // Utility to set the product load state for a category
  const setProductLoadState = useCallback(
    (categoryId: string, state: ProductLoadState) => {
      setProductLoadStates(prev => ({
        ...prev,
        [categoryId]: state,
      }));
    },
    []
  );

  return {
    // State
    categories,
    selectedCategory,
    loadingState,
    productLoadStates,

    // Actions
    handleCategorySelect,
    handleCategoryAdded,
    handleCategoryDeleted,
    handleCategoryUpdated,
    updateSelectedCategory,
    updateCategoryInList,
    setProductLoadState,
  };
};
