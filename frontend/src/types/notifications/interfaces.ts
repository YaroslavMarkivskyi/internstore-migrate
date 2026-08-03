export interface INotificationPayloadSSEData {
  id: number;
  event: string;
  status?: string;
  customer_name?: string;
}

export interface INotificationPayload {
  id: number; // order ID from SSE
  uniqueId: string; // unique identifier for React keys and operations
  event: string;
  status?: string;
  customerName?: string;
  isRead: boolean;
}

export interface INotificationPayloadState {
  notifications: INotificationPayload[];
}

export interface INotification {
  id: number;
  event: string;
  eventTime: string;
  payload: INotificationPayloadSSEData;
}

export interface INotificationRecipient {
  id: number;
  notification: INotification;
  isViewed: boolean;
}
