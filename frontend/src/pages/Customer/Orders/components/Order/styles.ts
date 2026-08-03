import {
  Accordion,
  AccordionSummary,
  Box,
  CircularProgress,
  styled,
  Table,
  Typography,
} from '@mui/material';

import ButtonCustomer from '@components/UI/customer/ButtonCustomer';
import StripeIcon from '@components/UI/icons/StripeIcon';
import colors from '@constants/colors';

export const OrderWrapper = styled(Accordion)({
  boxShadow: `0px 4px 15px ${colors.border}`,
  minHeight: 0,
  borderRadius: '5px',
  padding: '30px',
  '&.loading': {
    color: colors.placeholder,
  },
  '& .MuiAccordionSummary-root, & .MuiAccordionDetails-root': {
    minHeight: 0,
    padding: 0,
  },
  '& .MuiAccordionSummary-root': {
    '& .MuiAccordionSummary-content': {
      margin: 0,
    },
  },
  '& .MuiAccordionDetails-root': {
    paddingTop: '20px',
  },
  '&::before': {
    display: 'none',
  },
});

export const LoadingIndicator = styled(CircularProgress)({
  width: '5px',
  height: '5px',
  '& .MuiCircularProgress-svg': {
    width: '5px',
    height: '5px',
  },
});

export const OrderHeader = styled(AccordionSummary)({
  width: '100%',
});

export const OrderHeaderContent = styled(Box)({
  flex: 1,
  display: 'flex',
  alignItems: 'center',
});

export const OrderTitle = styled(Typography)({
  fontWeight: 500,
  fontSize: '16px',
});

export const OrderStatusWrapper = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  marginLeft: 'auto',
  marginRight: '20px',
});

export const OrderStatusDescriptionText = styled(Typography)({
  fontSize: '14px',
  color: colors.placeholder,
});

export const DividerHorizontal = styled(Box)({
  width: '100%',
  height: '1px',
  background: colors.backgroundDisabled,
});

export const OrderContent = styled(Box)({
  marginTop: '20px',
  display: 'flex',
  gap: '30px',
});

export const ContactDetailsWrapper = styled(Box)({
  flex: 5,
  display: 'flex',
  flexDirection: 'column',
  gap: '20px',
  borderRight: `1px solid ${colors.backgroundDisabled}`,
  paddingRight: '30px',
});

export const ContactDetailsRow = styled(Box)({
  display: 'flex',
  alignItems: 'flex-start',
});

export const ContactDetailsTextTitle = styled(Typography)({
  width: '50%',
  fontWeight: 500,
  fontSize: '14px',
});

export const ContactDetailsText = styled(Typography)({
  width: '50%',
  fontSize: '14px',
});

export const ProductsWrapper = styled(Box)({
  flex: 9,
  display: 'flex',
  flexDirection: 'column',
  gap: '20px',
});

export const OrderTable = styled(Table)({
  minHeight: '100px',
  '& .MuiTableCell-root': {
    borderBottom: 'None',
    paddingTop: '8px',
    paddingBottom: '8px',
  },
  '& .MuiTableCell-head': {
    fontWeight: 500,
    fontSize: '16px',
    paddingBottom: '12px',
  },
  '&.loading': {
    '& .MuiTableCell-head': {
      color: colors.placeholder,
    },
  },
});

export const ProductWrapper = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
});

export const ImageCellWrapper = styled(Box)({
  width: '50px',
  height: '50px',
});

export const ImageCell = styled('img')({
  width: '50px',
  height: '50px',
  objectFit: 'contain',
});

export const TableBottomWrapper = styled(Box)({
  width: '100%',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  alignItems: 'center',
});

export const TotalsRow = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
});

export const TotalsText = styled(Typography)({
  fontWeight: 500,
  fontSize: '16px',
});

export const ControlsWrapper = styled(Box)({
  marginTop: 'auto',
  marginLeft: 'auto',
});

export const ControlsButton = styled(ButtonCustomer)({
  paddingLeft: '30px',
  paddingRight: '30px',
});

export const PayWithStripeButton = styled(ControlsButton)({
  background: colors.backgroundDisabled,
  '&.MuiButton-text': {
    fontSize: '16px',
    '&:hover': {
      background: colors.backgroundDisabledHover,
    },
  },
});

export const PayWithStripeIcon = styled(StripeIcon)({
  marginLeft: '10px',
});
