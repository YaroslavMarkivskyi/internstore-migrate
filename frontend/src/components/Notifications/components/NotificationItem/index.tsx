import { useDispatch } from 'react-redux';

import { Circle, MarkEmailRead } from '@mui/icons-material';

import { markAsRead } from '@store/reducers/notifications';

import {
  MarkReadButton,
  NotificationContent,
  NotificationItemContainer,
  NotificationMeta,
  NotificationText,
  OrderId,
  ReadIndicatorContainer,
  StyledChip,
  UnreadDot,
} from './styles';

import { INotificationPayload } from 'src/types/notifications/interfaces';

interface NotificationItemProps {
  notification: INotificationPayload;
}

export const NotificationItem = ({ notification }: NotificationItemProps) => {
  const dispatch = useDispatch();

  const handleMarkAsRead = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!notification.isRead) {
      dispatch(markAsRead(notification.uniqueId));
    }
  };

  const getEventDisplayText = (
    event: string,
    customerName?: string,
    status?: string
  ) => {
    switch (event) {
      case 'order_created':
        return `New order ${customerName ? `from ${customerName}` : `#${notification.id}`}`;
      case 'order_status_updated':
        return `Order #${notification.id} ${status ? `marked as ${status}` : 'status updated'}`;
      default:
        return `Order #${notification.id} - ${event.replace(/_/g, ' ')}`;
    }
  };

  const getEventColor = (event: string) => {
    switch (event) {
      case 'order_created':
        return 'success';
      case 'order_status_updated':
        return 'info';
      default:
        return 'default';
    }
  };

  return (
    <NotificationItemContainer isRead={notification.isRead}>
      {/* Read/Unread Indicator */}
      <ReadIndicatorContainer>
        {!notification.isRead && (
          <UnreadDot>
            <Circle fontSize="inherit" />
          </UnreadDot>
        )}
      </ReadIndicatorContainer>

      {/* Notification Content */}
      <NotificationContent>
        <NotificationText variant="body2" isRead={notification.isRead}>
          {getEventDisplayText(
            notification.event,
            notification.customerName,
            notification.status
          )}
        </NotificationText>

        <NotificationMeta>
          <StyledChip
            label={notification.event.replace(/_/g, ' ')}
            size="small"
            color={getEventColor(notification.event)}
            variant="outlined"
          />

          <OrderId variant="caption" color="text.secondary">
            Order #{notification.id}
          </OrderId>
        </NotificationMeta>
      </NotificationContent>

      {/* Mark as Read Button */}
      {!notification.isRead && (
        <MarkReadButton
          size="small"
          onClick={handleMarkAsRead}
          title="Mark as read"
        >
          <MarkEmailRead fontSize="small" />
        </MarkReadButton>
      )}
    </NotificationItemContainer>
  );
};
