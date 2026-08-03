import { Box, Chip, IconButton, styled, Typography } from '@mui/material';

interface NotificationItemContainerProps {
  isRead: boolean;
}

interface NotificationTextProps {
  isRead: boolean;
}

export const NotificationItemContainer = styled(
  Box
)<NotificationItemContainerProps>(({ theme, isRead }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(2),
  padding: theme.spacing(2),
  borderBottom: '1px solid',
  borderColor: theme.palette.divider,
  backgroundColor: isRead ? 'transparent' : theme.palette.action.hover,
  transition: 'background-color 0.2s ease',
  '&:hover': {
    backgroundColor: theme.palette.action.selected,
  },
  '&:last-child': {
    borderBottom: 'none',
  },
}));

export const ReadIndicatorContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  marginTop: theme.spacing(0.5),
}));

export const UnreadDot = styled(Box)(({ theme }) => ({
  fontSize: 8,
  color: theme.palette.primary.main,
}));

export const NotificationContent = styled(Box)(() => ({
  flex: 1,
  minWidth: 0,
}));

export const NotificationText = styled(Typography)<NotificationTextProps>(
  ({ theme, isRead }) => ({
    fontWeight: isRead ? 'normal' : 500,
    color: isRead ? theme.palette.text.secondary : theme.palette.text.primary,
    marginBottom: theme.spacing(0.5),
  })
);

export const NotificationMeta = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(1),
  flexWrap: 'wrap',
}));

export const StyledChip = styled(Chip)(() => ({
  fontSize: '0.75rem',
  height: 20,
}));

export const OrderId = styled(Typography)(() => ({
  fontSize: '0.75rem',
}));

export const MarkReadButton = styled(IconButton)(({ theme }) => ({
  opacity: 0.7,
  '&:hover': {
    opacity: 1,
    backgroundColor: theme.palette.action.hover,
  },
}));
