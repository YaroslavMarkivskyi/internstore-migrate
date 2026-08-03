import { Box, MenuItem } from '@mui/material';
import { styled } from '@mui/material/styles';

import colors from '../../../../constants/colors';

export const OptionItem = styled(MenuItem)({
  padding: '14px 12px',
  '& .MuiTypography-root': {
    color: colors.text100,
    fontSize: '14px',
  },
  '&.Mui-selected:hover': {
    backgroundColor: colors.backgroundDisabled,
  },
  '& .Mui-disabled': {
    color: colors.placeholder,
    padding: 0,
  },
  '&.Mui-selected': {
    backgroundColor: colors.secondary.accent100,
    fontWeight: 500,
    '& .MuiTypography-root': {
      color: 'white',
    },
    '&:hover': {
      backgroundColor: colors.secondary.accent200,
    },
    '& .Mui-disabled': {
      color: 'white',
    },
  },
});

export const StartComponentWrapper = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginRight: 10,
});
