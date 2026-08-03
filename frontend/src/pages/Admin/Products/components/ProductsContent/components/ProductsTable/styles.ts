import {
  Box,
  IconButton,
  TableContainer as MuiTableContainer,
  Paper,
  styled,
  TableCell,
  TableRow,
  Typography,
} from '@mui/material';

// Table container
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

// Table header
export const TableHeadCell = styled(Typography)({
  fontWeight: 600,
});

export const TableHeadCellWithSort = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  fontWeight: 600,
});

export const TableSortButton = styled(IconButton)({
  marginLeft: 4,
  padding: 2,
  '& img': {
    width: 15,
    height: 18,
    display: 'block',
  },
});

// Table rows and cells
export const StyledTableRow = styled(TableRow)({
  '&:hover': {
    backgroundColor: '#F8F8FB',
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
