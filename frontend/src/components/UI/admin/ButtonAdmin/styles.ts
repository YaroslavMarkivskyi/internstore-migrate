import { Button } from '@mui/material';
import { styled } from '@mui/material/styles';

import colors from '../../../../constants/colors';

export const ButtonBase = styled(Button)({
  padding: '10px 14px',
  borderRadius: '10px',
  fontSize: '16px',
  textTransform: 'none',
  color: 'black',
  '&.MuiButton-text': {
    color: colors.secondary.accent100,
    fontSize: '14px',
    fontWeight: 500,
    '&:hover': {
      backgroundColor: colors.backgroundDisabled,
    },
  },
  '&.MuiButton-outlined': {
    border: `1px solid ${colors.secondary.accent100}`,
    fontWeight: 400,
    '&:hover': {
      background: colors.backgroundDisabled,
    },
  },
  '&.MuiButton-contained': {
    color: 'white',
    fontWeight: 500,
    backgroundColor: colors.secondary.accent100,
  },
  '&.Mui-disabled': {
    color: colors.textDisabled100,
    border: 'none',
  },
  '&.MuiButton-contained.Mui-disabled': {
    backgroundColor: colors.backgroundDisabled,
  },
  '&.MuiButton-outlined.Mui-disabled': {
    border: `1px solid ${colors.backgroundDisabled}`,
  },
  '&.MuiButton-text.Mui-disabled': {
    color: colors.textDisabled200,
  },
});
