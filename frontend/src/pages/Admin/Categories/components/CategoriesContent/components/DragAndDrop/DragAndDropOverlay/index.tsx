import { memo } from 'react';

import { DragOverlay } from '@dnd-kit/core';

import { DraggingProductItem } from '../DraggingProductItem';

import { Product } from '../../../types';

interface DragAndDropOverlayProps {
  activeProduct: Product | null;
}

/**
 * Component that renders the dragging overlay when moving products
 */
export const DragAndDropOverlay = memo(
  ({ activeProduct }: DragAndDropOverlayProps) => {
    return (
      <DragOverlay
        dropAnimation={{
          duration: 300,
          easing: 'cubic-bezier(0.18, 0.67, 0.6, 1.22)', // Bouncy effect
        }}
      >
        {activeProduct && <DraggingProductItem product={activeProduct} />}
      </DragOverlay>
    );
  }
);
