import { useCallback, useState } from 'react';

import {
  DragEndEvent,
  DragStartEvent,
  MouseSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';

import { Category, Product } from '../types';

interface UseDragAndDropProps {
  categories: Category[];
  selectedCategory: Category | null;
  handleMoveProducts: (
    sourceCategory: Category,
    productIds: string[],
    targetCategoryId: string
  ) => Promise<void>;
}

interface UseDragAndDropReturn {
  sensors: ReturnType<typeof useSensors>;
  activeProduct: Product | null;
  handleDragStart: (event: DragStartEvent) => void;
  handleDragEnd: (event: DragEndEvent) => void;
}

/**
 * Hook for handling drag and drop functionality for products
 */
export const useDragAndDrop = ({
  categories,
  selectedCategory,
  handleMoveProducts,
}: UseDragAndDropProps): UseDragAndDropReturn => {
  const [activeProduct, setActiveProduct] = useState<Product | null>(null);

  // Configure the sensors for drag operations with improved constraints
  const mouseSensor = useSensor(MouseSensor, {
    // Require minimal movement to activate (almost instant)
    activationConstraint: {
      distance: 1,
      // No delay for instant dragging
      tolerance: 5,
    },
  });

  const sensors = useSensors(mouseSensor);

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const { active } = event;

      // Check if we have product data in the draggable's data property
      if (
        active.data.current?.type === 'product' &&
        active.data.current?.product
      ) {
        // Set the active product directly from the data
        setActiveProduct(active.data.current.product);
      } else {
        // Fallback to the previous approach for compatibility
        const productId = active.id.toString().split('-')[1];

        // Find the product that is being dragged
        const sourceCategory = categories.find(cat =>
          cat.products?.some(product => product.id === productId)
        );

        if (sourceCategory && sourceCategory.products) {
          const product = sourceCategory.products.find(p => p.id === productId);
          if (product) {
            setActiveProduct(product);
          }
        }
      }
    },
    [categories]
  );

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      const { active, over } = event;

      // Clear the active product state
      setActiveProduct(null);

      // Ensure we have a valid drop target
      if (!over) return;

      let productId: string;
      let targetCategoryId: string;

      // Check if we're using the data property for the product
      if (
        active.data.current?.type === 'product' &&
        active.data.current?.product
      ) {
        productId = active.data.current.product.id;
      } else {
        // Fallback to parsing the ID from the string
        productId = active.id.toString().split('-')[1];
      }

      // Check if we're using the data property for the category
      if (
        over.data.current?.type === 'category' &&
        over.data.current?.category
      ) {
        targetCategoryId = over.data.current.category.id;
      } else {
        // Fallback to parsing the ID from the string
        targetCategoryId = over.id.toString().split('-')[1];
      }

      // Verify that we can only drop products onto categories that accept products
      if (
        over.data.current?.accepts &&
        !over.data.current.accepts.includes('product')
      ) {
        return;
      }

      // If dragging to the same category, do nothing
      if (selectedCategory?.id === targetCategoryId) return;

      // Find the product in the current category
      const sourceCategory = categories.find(cat =>
        cat.products?.some(product => product.id === productId)
      );

      if (!sourceCategory || !sourceCategory.products) return;

      // Move the product
      await handleMoveProducts(sourceCategory, [productId], targetCategoryId);

      // We don't need to automatically select the target category here
      // The handleMoveProducts function now properly updates the target category with
      // accurate product count and product data, which will be displayed when the user
      // navigates to that category
    },
    [categories, selectedCategory, handleMoveProducts]
  );

  return {
    sensors,
    activeProduct,
    handleDragStart,
    handleDragEnd,
  };
};
