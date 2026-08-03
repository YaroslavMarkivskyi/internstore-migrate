import { TableCell, Typography } from '@mui/material';
import { styled } from '@mui/system';

export const TableHeadCell = styled(Typography)({
  fontWeight: 600,
});

export const ActionsCell = styled(TableCell)({
  textAlign: 'right',
  width: '70px',
  padding: '0 16px',
});
