import { memo } from 'react';

import { useDroppable } from '@dnd-kit/core';
import { Box, CircularProgress, keyframes, Typography } from '@mui/material';

import colors from '../../../../../../../constants/colors';
import { Category } from '../../types';

import {
  CategoryCount,
  CategoryItem,
  CategoryListContainer,
  StyledList,
} from './styles';

// Define a pulsing animation keyframe
const pulseAnimation = keyframes`
  0% {
    box-shadow: 0 0 0 0 rgba(33, 150, 243, 0.4);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(33, 150, 243, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(33, 150, 243, 0);
  }
`;

interface CategoriesListProps {
  categories: Category[];
  selectedCategory: Category | null;
  onCategorySelect: (category: Category) => void;
  loading?: boolean;
}

// Component for a droppable category item
const DroppableCategory = ({
  category,
  isSelected,
  onClick,
}: {
  category: Category;
  isSelected: boolean;
  onClick: () => void;
}) => {
  const {
    setNodeRef,
    isOver,
    over: _over,
  } = useDroppable({
    id: `category-${category.id}`,
    data: {
      type: 'category',
      category,
      accepts: ['product'],
    },
  });

  const computedStyle = {
    backgroundColor: isSelected
      ? colors.secondary.accent100
      : isOver
        ? '#e3f2fd'
        : 'transparent',
    boxShadow: isOver ? '0 0 0 2px #2196f3' : 'none',
    transition: 'all 0.2s ease',
    animation: isOver ? `${pulseAnimation} 1.5s infinite` : 'none',
    transform: isOver ? 'translateY(-2px)' : 'none',
    border: isOver
      ? '1px dashed #2196f3'
      : isSelected
        ? `1px solid ${colors.secondary.accent100}`
        : '1px solid transparent',
    position: 'relative',
    zIndex: isOver ? 1 : 'auto',
  };

  return (
    <CategoryItem
      ref={setNodeRef}
      onClick={onClick}
      sx={computedStyle}
      className={isSelected ? 'selected' : ''}
    >
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        width="100%"
      >
        <Box display="flex" alignItems="center">
          <Typography
            variant="body1"
            fontWeight={isSelected ? 600 : 400}
            color={isSelected ? '#FFFFFF' : 'inherit'}
            sx={{ marginLeft: 2 }}
          >
            {category.name}
          </Typography>
        </Box>
        <CategoryCount
          sx={{
            color: isSelected ? '#FFFFFF' : '#616161',
          }}
        >
          {category.productCount || 0}
        </CategoryCount>
      </Box>

      {/* Show a visual indicator when hovering */}
      {isOver && (
        <Box
          sx={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            width: '100%',
            height: '3px',
            backgroundColor: '#2196f3',
            transition: 'all 0.2s ease',
          }}
        />
      )}
    </CategoryItem>
  );
};

const CategoriesList = ({
  categories,
  selectedCategory,
  onCategorySelect,
  loading = false,
}: CategoriesListProps) => {
  return (
    <CategoryListContainer>
      {loading ? (
        <Box display="flex" justifyContent="center" p={3}>
          <CircularProgress size={30} />
        </Box>
      ) : (
        <StyledList>
          {categories.map(category => (
            <DroppableCategory
              key={category.id}
              category={category}
              isSelected={selectedCategory?.id === category.id}
              onClick={() => onCategorySelect(category)}
            />
          ))}
          {categories.length === 0 && (
            <Box py={2} textAlign="center">
              <Typography variant="body2" color="text.secondary">
                No categories found
              </Typography>
            </Box>
          )}
        </StyledList>
      )}
    </CategoryListContainer>
  );
};

export default memo(CategoriesList);
