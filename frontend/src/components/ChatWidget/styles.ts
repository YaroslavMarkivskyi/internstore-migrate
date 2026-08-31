import { Box, Fab, Paper, styled } from '@mui/material';

import colors from '@constants/colors';

export const LauncherButton = styled(Fab)({
  position: 'fixed',
  right: 24,
  bottom: 24,
  zIndex: 1300,
  backgroundColor: colors.secondary.accent100,
  color: '#FFFFFF',
  '&:hover': {
    backgroundColor: colors.secondary.accent200,
  },
});

export const Panel = styled(Paper)({
  position: 'fixed',
  right: 24,
  bottom: 24,
  zIndex: 1300,
  width: 360,
  maxWidth: 'calc(100vw - 48px)',
  height: 520,
  maxHeight: 'calc(100vh - 48px)',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  borderRadius: 12,
  boxShadow: '0px 12px 40px rgba(0, 0, 0, 0.18)',
});

export const Header = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '12px 16px',
  backgroundColor: colors.secondary.accent100,
  color: '#FFFFFF',
});

export const HeaderTitle = styled(Box)({
  fontSize: 16,
  fontWeight: 600,
});

export const StatusLine = styled(Box)({
  fontSize: 12,
  opacity: 0.85,
});

export const Body = styled(Box)({
  flex: 1,
  overflowY: 'auto',
  padding: 16,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  backgroundColor: colors.secondary.background,
});

export const Bubble = styled(Box, {
  shouldForwardProp: prop => prop !== 'mine',
})<{ mine: boolean }>(({ mine }) => ({
  alignSelf: mine ? 'flex-end' : 'flex-start',
  maxWidth: '80%',
  padding: '8px 12px',
  borderRadius: 12,
  fontSize: 14,
  lineHeight: 1.4,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  backgroundColor: mine ? colors.secondary.accent100 : '#FFFFFF',
  color: mine ? '#FFFFFF' : colors.text100,
  border: mine ? 'none' : `1px solid ${colors.border}`,
}));

export const SenderTag = styled(Box)({
  fontSize: 11,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: 0.4,
  color: colors.text500,
  marginBottom: 2,
});

export const EmptyState = styled(Box)({
  margin: 'auto',
  textAlign: 'center',
  fontSize: 13,
  color: colors.text500,
});

export const Footer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: 12,
  borderTop: `1px solid ${colors.border}`,
  backgroundColor: '#FFFFFF',
});
