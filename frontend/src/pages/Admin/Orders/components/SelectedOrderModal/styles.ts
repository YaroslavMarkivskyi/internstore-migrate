import ClearIcon from '@mui/icons-material/Clear';
import {
  Box,
  CircularProgress,
  IconButton,
  styled,
  Table,
  Typography,
} from '@mui/material';

import OrderStatus from '@components/UI/common/OrderStatus';
import colors from '@constants/colors';

export const ModalContainer = styled(Box)(({ theme }) => ({
  position: 'absolute',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  backgroundColor: 'white',
  boxShadow: '0px 4px 15px #565656',
  borderRadius: '5px',
  outline: 'none',
  maxWidth: '1164px',
  // maxHeight: '615px',
  display: 'flex',
  flexDirection: 'column',
  width: '100%',
  // height: '100%',

  // Responsive behavior for small screens
  [theme.breakpoints.down('lg')]: {
    maxWidth: 'calc(100% - 32px)',
  },
}));

export const ModalContent = styled(Box)({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  gap: '25px',
  padding: '0 40px 40px',
});

export const CloseModalButton = styled(IconButton)({
  marginLeft: 'auto',
  marginTop: '15px',
  marginRight: '15px',
});

export const CloseModalIcon = styled(ClearIcon)({
  fill: colors.secondary.accent100,
});

export const LoadingProgress = styled(CircularProgress)({
  position: 'absolute',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  outline: 'none',
});

export const SectionTitle = styled(Typography)({
  fontWeight: 500,
  fontSize: ' 18px',
  color: colors.dashboard,
});

export const OrderStatusCell = styled(OrderStatus)({
  '& .MuiTypography-root': {
    fontSize: '0.875rem',
  },
});

export const OrderTable = styled(Table)({
  '& .MuiTableCell-root': {
    borderBottom: 'None',
    paddingTop: '8px',
    paddingBottom: '8px',
  },
  '& .MuiTableCell-head': {
    fontWeight: 600,
    fontSize: '16px',
  },
  '&.loading': {
    '& .MuiTableCell-head': {
      color: colors.placeholder,
    },
  },
});

export const ProductsTableWrapper = styled(Box)({
  maxHeight: '150px', // TODO: REMOVE
  overflowY: 'auto',
  scrollbarWidth: 'thin',
});

export const DividerLine = styled(Box)({
  width: '100%',
  height: '1px',
  background: colors.secondary.accent900,
});

export const ControlsContainer = styled(Box)({
  margin: 'auto 0 0 auto',
  gap: '25px',
  display: 'flex',
  flexDirection: 'column',
  width: '30%',
});

export const ControlsRow = styled(Box)({
  display: 'flex',
  justifyContent: 'space-between',
  gap: '20px',
});

export const TotalText = styled(Typography)({
  fontWeight: 600,
  fontSize: '18px',
});

export const TableBottomWrapper = styled(Box)({
  width: '100%',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  alignItems: 'center',
});

export const ImageCell = styled('img')({
  width: '50px',
  height: '50px',
  objectFit: 'contain',
});
