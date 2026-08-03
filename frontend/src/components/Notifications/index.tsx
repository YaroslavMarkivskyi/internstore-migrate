import { useDispatch, useSelector } from 'react-redux';

import {
  DeleteOutlined,
  MarkEmailReadOutlined,
  NotificationsNone,
} from '@mui/icons-material';
import { Divider } from '@mui/material';

import {
  deleteAllRead,
  markAllAsRead,
  selectHasReadNotifications,
  selectNotifications,
  selectUnreadCount,
} from '@store/reducers/notifications';

import { NotificationItem } from './components/NotificationItem';
import {
  ActionButton,
  ActionButtonsContainer,
  EmptyIcon,
  EmptyStateContainer,
  EmptySubtitle,
  EmptyTitle,
  NotificationsContainer,
  NotificationsHeader,
  NotificationsList,
  NotificationsTitle,
} from './styles';

export const NotificationsPopup = () => {
  const dispatch = useDispatch();
  const notifications = useSelector(selectNotifications);
  const unreadCount = useSelector(selectUnreadCount);
  const hasReadNotifications = useSelector(selectHasReadNotifications);

  const handleMarkAllAsRead = () => {
    dispatch(markAllAsRead());
  };

  const handleDeleteAllRead = () => {
    dispatch(deleteAllRead());
  };

  return (
    <NotificationsContainer>
      {/* Header */}
      <NotificationsHeader>
        <NotificationsTitle>Notifications</NotificationsTitle>

        {/* Action Buttons */}
        {notifications.length > 0 && (
          <ActionButtonsContainer direction="row" spacing={1}>
            {unreadCount > 0 && (
              <ActionButton
                size="small"
                startIcon={<MarkEmailReadOutlined />}
                onClick={handleMarkAllAsRead}
              >
                Mark all read
              </ActionButton>
            )}

            {hasReadNotifications && (
              <ActionButton
                size="small"
                startIcon={<DeleteOutlined />}
                onClick={handleDeleteAllRead}
                color="error"
              >
                Clear read
              </ActionButton>
            )}
          </ActionButtonsContainer>
        )}
      </NotificationsHeader>

      <Divider />

      {/* Notifications List */}
      <NotificationsList>
        {notifications.length === 0 ? (
          <EmptyStateContainer>
            <EmptyIcon>
              <NotificationsNone fontSize="inherit" />
            </EmptyIcon>
            <EmptyTitle variant="body2" color="text.secondary">
              No notifications yet
            </EmptyTitle>
            <EmptySubtitle variant="caption" color="text.disabled">
              New notifications will appear here
            </EmptySubtitle>
          </EmptyStateContainer>
        ) : (
          notifications.map(notification => (
            <NotificationItem
              key={notification.uniqueId}
              notification={notification}
            />
          ))
        )}
      </NotificationsList>
    </NotificationsContainer>
  );
};
