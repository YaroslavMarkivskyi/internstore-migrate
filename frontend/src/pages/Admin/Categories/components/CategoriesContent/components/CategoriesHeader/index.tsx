import { memo, useRef, useState } from 'react';

import AddIcon from '@mui/icons-material/Add';
import { Box } from '@mui/material';

import { createCategory } from '@services/http/admin/categories';

import CategoriesInput from '../ProductsSection/components/CategoriesInput';

import ButtonAdmin from '../../../../../../../components/UI/admin/ButtonAdmin';
import { Category } from '../../types';

import { ButtonContainer, HeaderContainer, HeaderTitle } from './styles';

interface CategoriesHeaderProps {
  onCategoryAdded?: (newCategory: Category) => void;
  onAddProduct?: () => void;
  isProductButtonDisabled?: boolean;
}

const CategoriesHeader = ({
  onCategoryAdded,
  onAddProduct,
  isProductButtonDisabled = false,
}: CategoriesHeaderProps) => {
  const [showCategoryInput, setShowCategoryInput] = useState(false);
  const categoryBtnRef = useRef<HTMLButtonElement>(null);

  const handleAddCategory = () => {
    setShowCategoryInput(true);
  };

  const handleCancelCategoryInput = () => {
    setShowCategoryInput(false);
  };

  const handleSubmitCategory = async (name: string) => {
    const newCategory = await createCategory(name);
    setShowCategoryInput(false);

    // Pass the newly created category to the parent component
    if (onCategoryAdded) {
      onCategoryAdded({ ...newCategory, productCount: 0 });
    }
  };

  const handleAddProductClick = () => {
    if (onAddProduct) {
      onAddProduct();
    }
  };

  return (
    <HeaderContainer>
      <HeaderTitle>Categories</HeaderTitle>
      <ButtonContainer>
        <Box display="flex" gap="16px">
          <ButtonAdmin
            variant="outlined"
            endIcon={<AddIcon sx={{ ml: 1 }} />}
            onClick={handleAddProductClick}
            disabled={isProductButtonDisabled}
            sx={{ px: 3 }}
          >
            Add a product
          </ButtonAdmin>
          <ButtonAdmin
            ref={categoryBtnRef}
            variant="contained"
            endIcon={<AddIcon sx={{ ml: 1, color: 'white' }} />}
            onClick={handleAddCategory}
            disabled={showCategoryInput}
            sx={{ px: 3 }}
          >
            Add a category
          </ButtonAdmin>
        </Box>

        {showCategoryInput && (
          <CategoriesInput
            placeholder="Enter category name"
            position={{
              right: '0',
              top: '45px',
            }}
            onSubmit={handleSubmitCategory}
            onCancel={handleCancelCategoryInput}
          />
        )}
      </ButtonContainer>
    </HeaderContainer>
  );
};

export default memo(CategoriesHeader);
