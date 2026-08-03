import {
  Box,
  Button,
  Chip,
  IconButton,
  Stack,
  styled,
  Typography,
} from '@mui/material';

// NotificationsPopup styles
export const NotificationsContainer = styled(Box)(() => ({
  width: 350,
  maxHeight: 400,
}));

export const NotificationsHeader = styled(Box)(({ theme }) => ({
  padding: theme.spacing(2),
  paddingBottom: theme.spacing(1),
}));

export const NotificationsTitle = styled(Typography)(({ theme }) => ({
  marginBottom: theme.spacing(1),
  textAlign: 'center',
}));

export const ActionButtonsContainer = styled(Stack)(() => ({
  display: 'flex',
  justifyContent: 'space-around',
}));

export const ActionButton = styled(Button)(() => ({
  fontSize: '0.75rem',
  textTransform: 'none',
  minWidth: 'auto',
}));

export const NotificationsList = styled(Box)(({ theme }) => ({
  maxHeight: 300,
  overflowY: 'auto',
  '&::-webkit-scrollbar': {
    width: 6,
  },
  '&::-webkit-scrollbar-track': {
    backgroundColor: 'transparent',
  },
  '&::-webkit-scrollbar-thumb': {
    backgroundColor: theme.palette.action.disabled,
    borderRadius: 3,
    '&:hover': {
      backgroundColor: theme.palette.action.hover,
    },
  },
}));

export const EmptyStateContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  paddingTop: theme.spacing(4),
  paddingBottom: theme.spacing(4),
  paddingLeft: theme.spacing(2),
  paddingRight: theme.spacing(2),
  color: theme.palette.text.secondary,
}));

export const EmptyIcon = styled(Box)(({ theme }) => ({
  fontSize: 48,
  marginBottom: theme.spacing(2),
  opacity: 0.5,
}));

export const EmptyTitle = styled(Typography)(() => ({
  textAlign: 'center',
}));

export const EmptySubtitle = styled(Typography)(({ theme }) => ({
  textAlign: 'center',
  marginTop: theme.spacing(0.5),
}));

// NotificationItem styles
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
  alignItems: 'flex-start',
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
