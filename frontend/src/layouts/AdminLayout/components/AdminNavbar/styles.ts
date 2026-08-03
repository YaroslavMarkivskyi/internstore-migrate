import { Avatar, Box, IconButton, styled } from '@mui/material';

import colors from '@constants/colors';

// ------------------------------------------------------------
// HEADER STYLING
// ------------------------------------------------------------

export const HeaderContainer = styled(Box)({
  padding: '12px 16px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  borderBottom: `1px solid ${colors.border}`,
  backgroundColor: colors.primary.background,
  width: '100%',
  maxWidth: 1920,
  margin: '0 auto',
});

export const SearchContainer = styled(Box)({
  width: '30%',
  maxWidth: 360,
  minWidth: 200,
  display: 'flex',
  alignItems: 'center',
  padding: 0,
  margin: 0,
});

export const ActionsContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  '& > *:not(:last-child)': {
    marginRight: 16,
  },
});

export const ActionIconButton = styled(IconButton)({
  padding: 0,
  width: 36,
  height: 36,
  borderRadius: '50%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  boxShadow: '0 4px 8px rgba(0,0,0,0.15)',
  transition: 'all 0.2s ease',
  backgroundColor: 'transparent',
  '&:hover': {
    boxShadow: '0 6px 12px rgba(0,0,0,0.2)',
    backgroundColor: colors.primary.accent1000,
  },
});

export const UserAvatar = styled(Avatar)({
  width: 36,
  height: 36,
  marginLeft: 12,
});

// ------------------------------------------------------------
// CONSTANTS
// ------------------------------------------------------------

export const ICON_COLOR = colors.primary.accent100;
