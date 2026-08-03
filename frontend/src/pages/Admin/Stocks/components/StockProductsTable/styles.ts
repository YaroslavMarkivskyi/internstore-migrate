import {
  TableContainer as MuiTableContainer,
  Paper,
  styled,
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
