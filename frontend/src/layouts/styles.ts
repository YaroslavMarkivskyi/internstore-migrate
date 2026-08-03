import { Box, styled } from '@mui/material';

import colors from '@constants/colors';

// ------------------------------------------------------------
// LAYOUT CONTAINER STYLING
// ------------------------------------------------------------

export const LayoutContainer = styled(Box)({
  display: 'flex',
  minHeight: '100vh',
  backgroundColor: colors.secondary.background,
});

// ------------------------------------------------------------
// MAIN CONTENT STYLING
// ------------------------------------------------------------

export const MainContentContainer = styled(Box)({
  flexGrow: 1,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
});

// ------------------------------------------------------------
// PAGE CONTENT STYLING
// ------------------------------------------------------------

export const PageContentContainer = styled(Box)({
  flexGrow: 1,
  overflow: 'auto',
  backgroundColor: colors.secondary.background,
  display: 'flex',
  justifyContent: 'center',
  width: '100%',
  boxSizing: 'border-box',
});

export const ContentWrapper = styled(Box)({
  width: '100%',
  maxWidth: 1920,
  padding: '0 16px',
  boxSizing: 'border-box',
  display: 'flex',
  justifyContent: 'center',
  '& > main': {
    width: '100%',
    boxSizing: 'border-box',
  },
});
