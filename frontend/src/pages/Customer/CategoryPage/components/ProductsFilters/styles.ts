import { Box, styled } from '@mui/material';

import ButtonCustomer from '@components/UI/customer/ButtonCustomer';
import colors from '@constants/colors';

export const FilterTriggerBox = styled(ButtonCustomer)({
  display: 'flex',
  gap: '10px',
  minWidth: '200px',
  justifyContent: 'flex-start',
  alignItems: 'center',
  '&.MuiButton-outlined': {
    border: `1px solid ${colors.border}`,
  },
  '&.MuiButton-text': {
    color: colors.text100,
  },
});

export const FiltersWrapper = styled(Box)({
  width: '100%',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
});

export const FilterContainer = styled(Box)({
  display: 'flex',
  gap: '20px',
});
