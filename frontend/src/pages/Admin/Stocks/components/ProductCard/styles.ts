import { Box, styled, Table, Typography } from '@mui/material';

import colors from '@constants/colors';

export const ProductCardContainer = styled(Box)({
  position: 'relative',
  padding: '40px',
  background: 'white',
  boxShadow: `0px 4px 15px ${colors.border}`,
  borderRadius: '10px',
  marginBottom: '30px',
  minHeight: '200px',
  display: 'flex',
  flexDirection: 'row',
  columnGap: '40px',
  alignItems: 'flex-start',
  justifyContent: 'space-around',
});

export const ImageContainer = styled(Box)({
  padding: '10px',
  border: `1px solid ${colors.border}`,
  borderRadius: '5px',
  '& img': {
    maxWidth: '276px',
    margin: '0 auto',
  },
});

export const TableWrapper = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  rowGap: '30px',
});

export const ProductTitle = styled(Typography)({
  fontWeight: 500,
  fontSize: '16px',
});

export const StocksTable = styled(Table)({
  '& .MuiTableCell-root': {
    borderBottom: 'None',
    paddingTop: '8px',
    paddingBottom: '8px',
    '&.error': {
      color: colors.error100,
      fontWeight: 500,
    },
  },
  '& .MuiTableCell-head': {
    fontWeight: 600,
  },
});

export const CloseButtonWrapper = styled(Box)({
  position: 'absolute',
  top: '16px',
  right: '16px',
  zIndex: 1,
});
