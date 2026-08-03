import { createTheme } from '@mui/material';

import colors from './constants/colors';

export default createTheme({
  palette: {
    mode: 'light',
    background: {
      default: colors.primary.background,
    },
    success: {
      main: colors.success100,
    },
    warning: {
      main: colors.warning100,
    },
    error: {
      main: colors.error100,
    },
    text: {
      primary: colors.text100,
      disabled: colors.text400,
    },
  },
  typography: {
    fontFamily: ['Noto Sans', 'sans-serif'].join(','),
  },
});
