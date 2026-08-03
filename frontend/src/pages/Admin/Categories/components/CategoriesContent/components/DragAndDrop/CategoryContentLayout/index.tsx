import { memo, ReactNode } from 'react';

import { DndContext } from '@dnd-kit/core';

import { CategoriesContainer } from '../../../styles';

interface CategoryContentLayoutProps {
  sensors: any;
  onDragStart: (event: any) => void;
  onDragEnd: (event: any) => void;
  children: ReactNode;
}

/**
 * Layout component that establishes the drag-and-drop context for the Categories page
 */
export const CategoryContentLayout = memo(
  ({
    sensors,
    onDragStart,
    onDragEnd,
    children,
  }: CategoryContentLayoutProps) => {
    return (
      <DndContext
        sensors={sensors}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
      >
        <CategoriesContainer>{children}</CategoriesContainer>
      </DndContext>
    );
  }
);
