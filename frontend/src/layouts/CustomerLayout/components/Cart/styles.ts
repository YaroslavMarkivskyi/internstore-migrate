import ShoppingCartOutlinedIcon from '@mui/icons-material/ShoppingCartOutlined';
import {
  Badge,
  Box,
  IconButton,
  styled,
  Table,
  Typography,
} from '@mui/material';

import ButtonCustomer from '@components/UI/customer/ButtonCustomer';
import colors from '@constants/colors';

export const CartIcon = styled(ShoppingCartOutlinedIcon)(({ theme }) => ({
  margin: theme.spacing(0.5),
}));

export const CartBadge = styled(Badge)({
  '& .MuiBadge-badge': {
    backgroundColor: colors.warning100,
    fontSize: '12px',
    fontWeight: 600,
    color: colors.text100,
  },
});

export const ModalContent = styled(Box)({
  position: 'absolute',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  maxWidth: '650px',
  width: '100%',
  maxHeight: '60vh',
  background: 'white',
  boxShadow: '0px 4px 15px #565656',
  borderRadius: '5px',
  padding: '25px 25px 35px 30px',
  display: 'flex',
  flexDirection: 'column',
});

export const CartHeader = styled(Box)({
  display: 'grid',
  gridTemplateColumns: '1fr auto 1fr',
  alignItems: 'center',
  marginBottom: '40px',
});

export const CartTitle = styled(Typography)({
  gridColumn: 2,
  justifySelf: 'center',
  fontSize: '18px',
  fontWeight: 500,
});

export const CartCloseIconButton = styled(IconButton)({
  fill: colors.placeholder,
  gridColumn: 3,
  justifySelf: 'flex-end',
});

export const CartContent = styled(Box)({
  marginRight: '5px',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
});

export const TableWrapper = styled(Box)({
  overflowY: 'auto',
  scrollbarWidth: 'thin',
  display: 'flex',
  flexDirection: 'column',
});

export const CartTable = styled(Table)({
  '& .MuiTableCell-root': {
    borderBottom: 'None',
    padding: '8px 14px',
    '&.price': {
      fontWeight: 500,
    },
    '&.quantity': {
      paddingLeft: 0,
      paddingRight: 0,
    },
  },
});

export const ProductImage = styled('img')({
  width: '50px',
  height: '50px',
  objectFit: 'contain',
});

export const DeleteButton = styled(ButtonCustomer)({
  padding: '5px 10px',
});

export const CartFooter = styled(Box)({
  marginTop: '40px',
  marginLeft: 'auto',
  display: 'flex',
  alignItems: 'center',
  gap: '30px',
});

export const TotalWrapper = styled(Box)({
  display: 'flex',
  gap: '20px',
});

export const CartFooterText = styled(Typography)({
  fontWeight: 500,
  fontSize: '20px',
});

export const CheckoutButton = styled(ButtonCustomer)({
  paddingLeft: '32px',
  paddingRight: '32px',
  '&.MuiButton-contained': {
    fontWeight: 400,
  },
});

export const SecondaryText = styled(Typography)({
  margin: '0 auto',
  fontSize: '14px',
  color: colors.textDisabled100,
  textAlign: 'center',
});

export const LoadingContainer = styled(Box)({
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  zIndex: 100,
  background: 'rgba(0, 0, 0, 0.3)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
});
