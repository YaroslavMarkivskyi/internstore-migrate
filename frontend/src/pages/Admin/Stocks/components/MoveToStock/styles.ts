import ControlPointOutlinedIcon from '@mui/icons-material/ControlPointOutlined';
import { IconButton, Typography } from '@mui/material';
import { styled } from '@mui/material/styles';

import SelectFieldAdmin from '@components/UI/admin/SelectFieldAdmin';
import InputFieldCustomer from '@components/UI/customer/InputFieldCustomer';

export const StyledMoveToStockContainer = styled('div')({
  width: '350px',
  padding: '25px',
  borderRadius: '10px',
  boxShadow: '0px 4px 15px #E0E0E0',
  position: 'relative',
});

export const MoveToStockTitle = styled(Typography)({
  textAlign: 'center',
  marginBottom: '15px',
});

export const StyledMoveToStockCloseButton = styled(IconButton)({
  position: 'absolute',
  top: 15,
  right: 12,
  zIndex: 999,
});

export const MoveToStockText = styled(Typography)({
  fontSize: '14px',
  color: '#121212',
});

export const MoveFromInput = styled(InputFieldCustomer)({
  '& .MuiOutlinedInput-root': {
    borderRadius: '10px',
    width: '137px',
  },
  '& .MuiInputBase-input': {
    padding: '12px',
  },
  '&.MuiFormControl-root': {
    padding: '0',
  },
});

export const QuantityInput = styled(MoveFromInput)({
  '& .MuiInputBase-input': {
    textAlign: 'center',
  },
});

export const AddDestinationStockIcon = styled(ControlPointOutlinedIcon)({
  color: '#818181',
  marginLeft: '10px',
  // marginBottom: "10px",
});

export const TargetStockSelect = styled(SelectFieldAdmin)({
  '& .MuiInputBase-input': {
    padding: '12px',
  },
});
