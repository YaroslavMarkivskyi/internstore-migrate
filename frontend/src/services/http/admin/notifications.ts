import { ccApi as api } from '@services/http/api';

// No notifications REST API on the backend — the `notifications` service
// only has a Kafka consumer, no HTTP router (see
// internstore-migrate/services/notifications). Left as-is; will 404.
export const getUnreadNotifications = async () => {
  const resp = await api.get(`notifications/?is_viewed=false`);
  return resp.data;
};

export const markNotificationsAsRead = async (recipientIds: Array<number>) => {
  const resp = await api.patch('notifications/bulk_update/', {
    recipientIds: recipientIds,
  });
  return resp.data;
};
