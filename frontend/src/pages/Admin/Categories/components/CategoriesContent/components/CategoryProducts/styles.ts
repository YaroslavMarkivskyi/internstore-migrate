import {
  Box,
  Button,
  styled,
  TableCell,
  TableRow,
  Typography,
} from '@mui/material';

export const CategoryProductsContainer = styled(Box)(() => ({
  flex: 1,
  backgroundColor: '#ffffff',
  borderRadius: '8px',
  padding: '24px',
  boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.05)',
  display: 'flex',
  flexDirection: 'column',
  gap: '24px',
}));

export const HeaderBox = styled(Box)(() => ({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  width: '100%',
  marginBottom: '16px',
}));

export const CategoryNameWrapper = styled(Box)(({ theme }) => ({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  width: '100%',
  marginBottom: theme.spacing(2),
}));

export const HeaderTitle = styled(Typography)(() => ({
  fontSize: '18px',
  fontWeight: 600,
  color: '#10045C',
  fontFamily: '"Noto Sans", sans-serif',
}));

export const TableBox = styled(Box)(() => ({
  width: '100%',
  overflowX: 'auto',
}));

export const TableContainer = styled(Box)(() => ({
  width: '100%',
  fontSize: '14px',
}));

export const TableHeadCell = styled(Typography)(() => ({
  fontSize: '14px',
  fontWeight: 600,
  color: '#616161',
  fontFamily: '"Noto Sans", sans-serif',
}));

export const TableHeadCellWithSort = styled(Box)(() => ({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  fontSize: '14px',
  fontWeight: 600,
  color: '#616161',
  fontFamily: '"Noto Sans", sans-serif',
}));

export const TableSortButton = styled(Button)(() => ({
  minWidth: '24px',
  width: '24px',
  height: '24px',
  padding: 0,
  color: '#616161',
}));

export const StyledTableRow = styled(TableRow)(() => ({
  '&:nth-of-type(odd)': {
    backgroundColor: '#fafafa',
  },
  '&:hover': {
    backgroundColor: '#f5f5f5',
  },
  '&.Mui-selected': {
    backgroundColor: 'rgba(33, 150, 243, 0.08)',
    '&:hover': {
      backgroundColor: 'rgba(33, 150, 243, 0.12)',
    },
  },
  '& td': {
    padding: '12px 16px',
    fontSize: '14px',
    color: '#212121',
  },
}));

export const ProductImage = styled('img')(() => ({
  width: '48px',
  height: '48px',
  objectFit: 'cover',
  borderRadius: '4px',
}));

export const ActionsCell = styled(TableCell)(() => ({
  width: '48px',
  padding: '0 8px',
  textAlign: 'center',
  verticalAlign: 'middle',
}));

export const DragHandleCell = styled(TableCell)(() => ({
  width: '48px',
  padding: '0 8px',
  textAlign: 'center',
  cursor: 'grab',
}));

export const CheckboxCell = styled(TableCell)(() => ({
  width: '48px',
  padding: '0 8px',
  textAlign: 'center',
  verticalAlign: 'middle',
}));

export const PaginationWrapper = styled(Box)(() => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  width: '100%',
  marginTop: '20px',
  paddingTop: '20px',
  borderTop: '1px solid #e0e0e0',
  padding: '0 24px 16px',
}));
