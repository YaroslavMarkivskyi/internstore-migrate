import {
  Box,
  Divider,
  Paper,
  TableCell,
  TableContainer,
  Typography,
  TypographyProps,
} from '@mui/material';
import { styled } from '@mui/material/styles';

import colors from '@constants/colors';

import { cardStyle } from '../styles';

export const StyledPaper = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(2),
  margin: '0 0 24px 0',
  borderRadius: cardStyle.borderRadius,
  boxShadow: cardStyle.boxShadow,
}));

export const TitleContainer = styled('div')({
  display: 'flex',
  flexDirection: 'row',
  justifyContent: 'space-between',
  marginBottom: 16,
});

export const TitleText = styled(Typography)<TypographyProps>({
  color: colors.dashboard,
  fontWeight: 600,
});

export const TableDivider = styled(Divider)({
  margin: '0 0 16px 0',
  backgroundColor: colors.border,
});

export const StyledTableContainer = styled(TableContainer)({
  '& .MuiTableCell-root': {
    borderBottom: 'none',
  },
  '& .MuiTableRow-root': {
    '&:hover': {
      backgroundColor: '#F8F8FB',
    },
  },
});

export const StatusCell = styled(TableCell)({
  paddingTop: 10,
  paddingBottom: 10,
  verticalAlign: 'middle',
  '& > div': {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-start',
  },
});

export const RefreshCountdown = styled(Typography)({
  fontSize: 14,
  color: colors.text700,
  marginRight: 6,
});

export const RefreshContainer = styled(Box)({
  display: 'flex',
  flexDirection: 'row',
  alignItems: 'center',
});
