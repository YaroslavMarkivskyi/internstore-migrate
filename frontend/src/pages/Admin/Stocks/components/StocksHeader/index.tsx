import { memo } from 'react';

import { Typography } from '@mui/material';

import { pageTitle } from './styles';

const StocksHeader = () => {
  return (
    <Typography variant="h4" component="h1" sx={pageTitle}>
      Stocks
    </Typography>
  );
};

export default memo(StocksHeader);
