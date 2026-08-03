import { OrderStatus } from '../../../../../types/orders/types';

export const StatusesToHideControls: OrderStatus[] = [
  'done',
  'rejected',
  'pending',
  'cancelled',
];
export const CreateShipmentStatus: OrderStatus = 'paid';
export const SendInvoiceStatus: OrderStatus = 'new';
