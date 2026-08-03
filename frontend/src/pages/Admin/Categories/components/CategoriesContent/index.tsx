import { memo, useCallback, useEffect } from 'react';

import { useNavigate } from 'react-router-dom';

import { Box } from '@mui/material';

import CategoriesHeader from './components/CategoriesHeader';
import CategoriesList from './components/CategoriesList';
import { CategoryContentLayout } from './components/DragAndDrop/CategoryContentLayout';
import { DragAndDropOverlay } from './components/DragAndDrop/DragAndDropOverlay';
import { LoadingSpinner } from './components/LoadingSpinner';
import { ProductsSection } from './components/ProductsSection';
import { useCategories, useDragAndDrop, useProducts } from './hooks';
import { Category, Product, ProductLoadState } from './types';

/**
 * Main component for the Categories admin page
 */
const CategoriesContent = () => {
  const navigate = useNavigate();

  // Use our custom hooks
  const {
    categories,
    selectedCategory,
    loadingState,
    productLoadStates,
    handleCategorySelect,
    handleCategoryAdded,
    handleCategoryDeleted,
    handleCategoryUpdated,
    setProductLoadState,
    updateCategoryInList,
  } = useCategories();

  const {
    paginationState,
    loadingState: productsLoadingState,
    isMovingLastProduct,
    loadCategoryProducts,
    handlePageChange: handlePageChangeInternal,
    handleMoveProducts,
    handleDeleteProducts,
    handleUpdateCategoryProducts,
  } = useProducts({
    setProductLoadState,
    updateCategoryInList,
    categories,
  });

  const { sensors, activeProduct, handleDragStart, handleDragEnd } =
    useDragAndDrop({
      categories,
      selectedCategory,
      handleMoveProducts,
    });

  // Effect to load products when selectedCategory changes
  useEffect(() => {
    if (selectedCategory) {
      const loadState = productLoadStates[selectedCategory.id];

      // Make sure we always have the most recent product count
      const currentProductCount = selectedCategory.productCount || 0;

      // Always reload the products in these cases:
      // 1. No load state yet
      // 2. Load state is not 'loaded' or 'loading'
      // 3. The category has a product count but no products loaded
      if (
        !loadState ||
        (loadState !== ProductLoadState.Loaded &&
          loadState !== ProductLoadState.Loading) ||
        (currentProductCount > 0 &&
          (!selectedCategory.products ||
            selectedCategory.products.length === 0))
      ) {
        // Immediately load products when a category is selected
        loadCategoryProducts(selectedCategory);
      }
    }
  }, [selectedCategory, productLoadStates, loadCategoryProducts]);

  // Handle page change with the selected category
  const handlePageChange = useCallback(
    (newPage: number) => {
      if (selectedCategory) {
        handlePageChangeInternal(selectedCategory, newPage);
      }
    },
    [selectedCategory, handlePageChangeInternal]
  );

  const handleAddProduct = useCallback(() => {
    navigate('/admin/products/add');
  }, [navigate]);

  // Handler for moving products between categories
  const handleProductsMove = useCallback(
    (productIds: string[], targetCategoryId: string): Promise<void> => {
      if (!selectedCategory || productIds.length === 0) {
        return Promise.resolve();
      }

      // Store some information about the current state
      const sourceCategory = selectedCategory;

      // Always use the current selected category as source
      return handleMoveProducts(
        sourceCategory,
        productIds,
        targetCategoryId
      ).then(() => {
        // Mark the target category as needing loading when the user selects it later
        setProductLoadState(targetCategoryId, ProductLoadState.NotLoaded);

        // Stay on current category and reload it to reflect the changes
        // Call loadCategoryProducts but don't return its result
        loadCategoryProducts(sourceCategory);

        // Return void to satisfy the Promise<void> type
        return Promise.resolve();
      });
    },
    [
      selectedCategory,
      handleMoveProducts,
      loadCategoryProducts,
      setProductLoadState,
    ]
  );

  // Handler for deleting products
  const handleProductsDelete = useCallback(
    (productIds: string[]) => {
      if (selectedCategory) {
        return handleDeleteProducts(selectedCategory, productIds);
      }
      return Promise.resolve();
    },
    [selectedCategory, handleDeleteProducts]
  );

  if (loadingState.categories) {
    return <LoadingSpinner />;
  }

  // Calculate if products are loading
  const isProductsLoading =
    productsLoadingState.products ||
    (selectedCategory !== null &&
      productLoadStates[selectedCategory.id] === 'loading');

  // Adapter function for category updates
  const handleCategoryUpdateAdapter = (updatedCategory: Category) => {
    // Ensure we pass the id and the complete updatedCategory object
    // This will preserve all properties including productCount
    handleCategoryUpdated(updatedCategory.id, updatedCategory);
  };

  // Adapter function for product updates
  const handleProductsUpdateAdapter = (updatedProducts: Product[]) => {
    if (selectedCategory) {
      handleUpdateCategoryProducts(selectedCategory.id, updatedProducts);
    }
  };

  return (
    <CategoryContentLayout
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <CategoriesHeader
        onCategoryAdded={handleCategoryAdded}
        onAddProduct={handleAddProduct}
        isProductButtonDisabled={!selectedCategory}
      />

      <Box display="flex" gap="20px" width="100%">
        <CategoriesList
          categories={categories}
          selectedCategory={selectedCategory}
          onCategorySelect={handleCategorySelect}
          loading={loadingState.categories}
        />

        <ProductsSection
          selectedCategory={selectedCategory}
          allCategories={categories}
          loading={isProductsLoading}
          isUpdating={isMovingLastProduct}
          paginationState={paginationState}
          onCategoryDeleted={handleCategoryDeleted}
          onCategoryUpdated={handleCategoryUpdateAdapter}
          onProductsMove={handleProductsMove}
          onProductsDelete={handleProductsDelete}
          onPageChange={handlePageChange}
          setCategories={handleProductsUpdateAdapter}
          setProductLoadState={setProductLoadState}
          onCategorySelect={handleCategorySelect}
        />
      </Box>

      <DragAndDropOverlay activeProduct={activeProduct} />
    </CategoryContentLayout>
  );
};

export default memo(CategoriesContent);
