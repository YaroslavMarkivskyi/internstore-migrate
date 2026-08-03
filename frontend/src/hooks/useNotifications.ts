import { useEffect, useRef } from 'react';

import { useDispatch } from 'react-redux';

import { EventSourcePolyfill as EventSource } from 'event-source-polyfill';

import {
  getUnreadNotifications,
  markNotificationsAsRead,
} from '@services/http/admin/notifications';
import { SERVER_URL } from '@services/http/api';
import { addNotification } from '@store/reducers/notifications';

import {
  INotificationPayloadSSEData,
  INotificationRecipient,
} from 'src/types/notifications/interfaces';

interface UseNotificationsProps {
  accessToken: string | null;
  isAdmin: boolean;
  enabled?: boolean;
}

const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY_MS = 5000;

export const useNotifications = ({
  accessToken,
  isAdmin,
  enabled = true,
}: UseNotificationsProps) => {
  const dispatch = useDispatch();
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );

  const createSSEConnection = (token: string): EventSource => {
    const eventSource = new EventSource(`${SERVER_URL}notifications/live/`, {
      headers: { Authorization: `Bearer ${token}` },
      withCredentials: true,
    });

    eventSource.onmessage = event => {
      try {
        const parsedData: INotificationPayloadSSEData = JSON.parse(event.data);
        dispatch(addNotification(parsedData));
      } catch (parseError) {
        console.error('Failed to parse SSE data', parseError);
      }
    };

    eventSource.onerror = error => {
      console.error('SSE connection failed, trying to reconnect');
      eventSource.close();
      eventSourceRef.current = null;

      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttemptsRef.current++;
        reconnectTimeoutRef.current = setTimeout(() => {
          if (accessToken) {
            eventSourceRef.current = createSSEConnection(accessToken);
          }
        }, RECONNECT_DELAY_MS);
      } else {
        console.error('EventSource error:', error);
      }
    };

    return eventSource;
  };

  const fetchAndProcessHistoricalNotifications = async (): Promise<void> => {
    try {
      const unreadNotifications: INotificationRecipient[] =
        await getUnreadNotifications();

      if (unreadNotifications.length === 0) return;

      const recipientIds: number[] = [];

      unreadNotifications.forEach(recipient => {
        recipientIds.push(recipient.id);

        const sseData: INotificationPayloadSSEData = {
          id: recipient.notification.payload.id,
          event: recipient.notification.payload.event,
          status: recipient.notification.payload.status,
          customer_name: recipient.notification.payload.customer_name,
        };

        dispatch(addNotification(sseData));
      });

      try {
        await markNotificationsAsRead(recipientIds);
      } catch (markReadError) {
        console.error('Failed to mark notifications as read:', markReadError);
      }
    } catch (fetchError) {
      console.error('Failed to fetch historical notifications:', fetchError);
      throw fetchError;
    }
  };

  const initializeNotifications = async (token: string): Promise<void> => {
    try {
      await fetchAndProcessHistoricalNotifications();
    } catch (historicalError) {
      console.error(
        'Historical notification fetch failed, continuing with SSE...',
        historicalError
      );
    }

    try {
      eventSourceRef.current = createSSEConnection(token);
      reconnectAttemptsRef.current = 0;
    } catch (sseError) {
      console.error('Failed to initialize SSE connection:', sseError);
    }
  };

  const cleanup = (): void => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    reconnectAttemptsRef.current = 0;
  };

  useEffect(() => {
    if (!enabled || !isAdmin || !accessToken) {
      cleanup();
      return;
    }

    initializeNotifications(accessToken);

    return cleanup;
  }, [accessToken, isAdmin, enabled, dispatch]);

  return {
    cleanup,
    isConnected: () => eventSourceRef.current?.readyState === EventSource.OPEN,
  };
};
