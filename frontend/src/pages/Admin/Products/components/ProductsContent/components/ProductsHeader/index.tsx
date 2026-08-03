import { memo } from 'react';

import { Typography } from '@mui/material';

import { pageTitle } from './styles';

const ProductsHeader = () => {
  return (
    <Typography variant="h4" component="h1" sx={pageTitle}>
      Products
    </Typography>
  );
};

export default memo(ProductsHeader);
