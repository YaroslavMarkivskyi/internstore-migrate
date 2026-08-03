import { createSlice, PayloadAction } from '@reduxjs/toolkit';

import DOMPurify from 'dompurify';

import { RootState } from '../store';

import {
  INotificationPayload,
  INotificationPayloadSSEData,
  INotificationPayloadState,
} from '../../types/notifications/interfaces';

const MAX_NOTIFICATIONS = 100;

const initialState: INotificationPayloadState = {
  notifications: [],
};

// Helper function to validate event type
const isValidEvent = (event: string): boolean => {
  const validEvents = ['order_created', 'order_status_updated'];
  return validEvents.includes(event) || /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(event);
};

const notificationsSlice = createSlice({
  name: 'notifications',
  initialState,
  reducers: {
    addNotification: (
      state,
      action: PayloadAction<INotificationPayloadSSEData>
    ) => {
      const sseData = action.payload;

      // Validate required fields
      if (typeof sseData.id !== 'number' || !sseData.event) {
        console.error('Invalid notification data received:', sseData);
        return;
      }

      // Validate event type
      if (!isValidEvent(sseData.event)) {
        console.error('Invalid event type received:', sseData.event);
        return;
      }

      const notification: INotificationPayload = {
        id: sseData.id,
        uniqueId: `${sseData.id}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        event: sseData.event,
        status: DOMPurify.sanitize(sseData.status ?? ''),
        customerName: DOMPurify.sanitize(sseData.customer_name ?? ''),
        isRead: false,
      };

      // Add to beginning of array (newest first)
      state.notifications.unshift(notification);

      // Limit total notifications
      if (state.notifications.length > MAX_NOTIFICATIONS) {
        state.notifications = state.notifications.slice(0, MAX_NOTIFICATIONS);
      }
    },

    markAsRead: (state, action: PayloadAction<string>) => {
      const uniqueId = action.payload;
      const notification = state.notifications.find(
        n => n.uniqueId === uniqueId
      );
      if (notification) {
        notification.isRead = true;
      }
    },

    markAllAsRead: state => {
      state.notifications.forEach(notification => {
        notification.isRead = true;
      });
    },

    deleteAllRead: state => {
      state.notifications = state.notifications.filter(
        notification => !notification.isRead
      );
    },

    clearAllNotifications: state => {
      state.notifications = [];
    },
  },
});

export const {
  addNotification,
  markAsRead,
  markAllAsRead,
  deleteAllRead,
  clearAllNotifications,
} = notificationsSlice.actions;

// Selectors
export const selectNotifications = (state: RootState) =>
  state.notifications.notifications;

export const selectUnreadNotifications = (state: RootState) =>
  state.notifications.notifications.filter(
    notification => !notification.isRead
  );

export const selectUnreadCount = (state: RootState) =>
  state.notifications.notifications.filter(notification => !notification.isRead)
    .length;

export const selectReadNotifications = (state: RootState) =>
  state.notifications.notifications.filter(notification => notification.isRead);

export const selectHasReadNotifications = (state: RootState) =>
  state.notifications.notifications.some(notification => notification.isRead);

export default notificationsSlice.reducer;
