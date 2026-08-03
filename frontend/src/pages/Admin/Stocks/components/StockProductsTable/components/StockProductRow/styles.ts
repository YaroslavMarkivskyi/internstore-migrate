import { styled, TableCell, TableRow, Typography } from '@mui/material';

import colors from '@constants/colors';

export const StyledTableRow = styled(TableRow)({
  '&:hover': {
    backgroundColor: '#F8F8FB',
    cursor: 'pointer',
  },
  '&.selected-row': {
    backgroundColor: colors.secondary.accent100,
    '&:hover': {
      backgroundColor: colors.secondary.accent200,
    },
    '& .MuiTableCell-root, .MuiSvgIcon-root': {
      color: 'white',
    },
  },
});

export const ProductImage = styled('img')({
  width: 60,
  height: 40,
  objectFit: 'contain',
  borderRadius: '4px',
});

export const ProductNameCell = styled(Typography)({
  fontWeight: 500,
});

export const ActionsCell = styled(TableCell)({
  textAlign: 'right',
  width: '70px',
  padding: '0 16px',
});
