import { Box, styled, Table } from '@mui/material';

export const ProductsTable = styled(Table)({
  '& .MuiTableCell-root': {
    borderBottom: 'none',
    paddingTop: '8px',
    paddingBottom: '8px',
  },
  '& .MuiTableCell-head': {
    fontWeight: 600,
    fontSize: '16px',
  },
});

export const ProductsTableWrapper = styled(Box)({
  maxHeight: '500px',
  overflowY: 'auto',
  scrollbarWidth: 'thin',
});

export const ProductImage = styled('img')({
  width: '50px',
  height: '50px',
  objectFit: 'contain',
});
