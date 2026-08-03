import { useNavigate, useOutletContext } from 'react-router';

import { Typography } from '@mui/material';

import { imagePlaceholderUrl } from '@constants/urls';
import { CategoryContextType } from '@pages/Customer/CategoryMenu';
import {
  CategoriesContainer,
  CategoryCard,
  CategoryImage,
  CategoryTitle,
  HomepageWrapper,
  NothingText,
} from '@pages/Customer/Homepage/styles';

import RecentlyAddedProducts from './RecentlyAddedProducts';
import RecentlyViewedProducts from './RecentlyViewedProducts';

const Homepage = () => {
  const { categories } = useOutletContext<CategoryContextType>();
  const navigate = useNavigate();

  const handleCategoryClick = (categoryId: string) => {
    return () => navigate(`/categories/${categoryId}`);
  };

  return (
    <>
      {categories && categories.length > 0 ? (
        <HomepageWrapper>
          <RecentlyAddedProducts />
          <RecentlyViewedProducts />

          <Typography>Catalogue</Typography>
          <CategoriesContainer>
            {categories.map(category => (
              <CategoryCard
                key={category.id}
                onClick={handleCategoryClick(category.id)}
              >
                <CategoryImage
                  src={category.image ? category.image : imagePlaceholderUrl}
                  alt={category.name}
                />
                <CategoryTitle>{category.name}</CategoryTitle>
              </CategoryCard>
            ))}
          </CategoriesContainer>
        </HomepageWrapper>
      ) : (
        <NothingText>There is nothing here yet...</NothingText>
      )}
    </>
  );
};

export default Homepage;
