import {
  TableContainer as MuiTableContainer,
  Paper,
  styled,
  TableRow,
  Typography,
} from '@mui/material';

import OrderStatus from '@components/UI/common/OrderStatus';

export const TableBox = styled(Paper)({
  margin: '0 0 24px 0',
  padding: 16,
  borderRadius: '8px',
  boxShadow: '0px 4px 15px 0px #E0E0E0',
  width: '100%',
  '& .MuiTableCell-root': {
    fontFamily: '"Noto Sans", sans-serif',
  },
});

export const TableContainer = styled(MuiTableContainer)({
  '& .MuiTableCell-root': {
    borderBottom: 'none',
  },
});

export const TableHeadCell = styled(Typography)({
  fontWeight: 600,
});

export const StyledTableRow = styled(TableRow)({
  cursor: 'pointer',
  '&:hover': {
    backgroundColor: '#F8F8FB',
  },
});

export const OrderStatusCell = styled(OrderStatus)({
  justifyContent: 'flex-start',
  '& .MuiTypography-root': {
    fontSize: '0.875rem',
  },
});
