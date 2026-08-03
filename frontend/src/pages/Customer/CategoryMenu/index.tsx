import { useEffect, useState } from 'react';

import { Outlet, useLocation, useNavigate } from 'react-router';

import { CircularProgress, Typography } from '@mui/material';

import SideMenu from '@components/SideMenu';
import { getCategoriesPreview } from '@services/http/admin/categories';
import showToast from '@utils/showToast';

import { ICategoryPreview } from '../../../types/categories/interfaces';

export type CategoryContextType = { categories: ICategoryPreview[] | null };

const CategoryMenu = () => {
  const [categories, setCategories] = useState<ICategoryPreview[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const navigate = useNavigate();
  const { pathname } = useLocation();

  const fetchCategories = async () => {
    setIsLoading(true);
    try {
      const data = await getCategoriesPreview();
      setCategories(data);
    } catch {
      showToast({
        message: 'Error connecting to the server',
        type: 'error',
      });
    }
    setIsLoading(false);
  };

  const handleLinkClick = (path: string) => {
    return () => {
      navigate(path);
    };
  };

  useEffect(() => {
    void fetchCategories();
  }, []);

  return isLoading ? (
    <CircularProgress sx={{ m: 'auto' }} />
  ) : (
    <SideMenu
      title="Catalogue"
      menuContent={
        categories.length > 0 ? (
          categories.map(category => (
            <a
              key={category.id}
              className={
                pathname === `/categories/${category.id}` ? 'active' : ''
              }
              onClick={handleLinkClick(`/categories/${category.id}`)}
            >
              {category.name}
            </a>
          ))
        ) : (
          <Typography>No categories yet!</Typography>
        )
      }
      content={
        <Outlet context={{ categories } satisfies CategoryContextType} />
      }
    />
  );
};

export default CategoryMenu;
