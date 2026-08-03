import { Box, Divider, Paper, styled } from '@mui/material';

import colors from '@constants/colors';

// ------------------------------------------------------------
// SIDEBAR CONTAINER STYLING
// ------------------------------------------------------------

export const SidebarContainer = styled(Paper)({
  width: 240,
  height: '100vh',
  borderRadius: 0,
  display: 'flex',
  flexDirection: 'column',
  backgroundColor: colors.primary.background,
  borderRight: `1px solid ${colors.border}`,
  paddingTop: 16,
  position: 'sticky',
  top: 0,
  zIndex: 10,
  boxShadow: 'none',
});

// ------------------------------------------------------------
// MENU STYLING
// ------------------------------------------------------------

export const MenuList = styled(Box)({
  flex: '1 1 auto',
  paddingLeft: 8,
  paddingRight: 8,
  overflowY: 'auto',
  marginTop: 40,
});

export const MenuIcon = styled('div')({
  '& img': {
    width: 18,
    height: 18,
    display: 'block',
  },
});

export const MenuDivider = styled(Divider)({
  marginTop: 8,
  marginBottom: 8,
  backgroundColor: colors.border,
});
