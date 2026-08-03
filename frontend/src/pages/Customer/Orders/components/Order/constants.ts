import { OrderStatus } from '../../../../../types/orders/types';

export const statusDescriptionMap: Record<OrderStatus, string> = {
  new: '(pending confirmation from the seller)',
  pending: '(pending payment)',
  rejected: '(no available products left)',
  done: '',
  cancelled: '',
  paid: '',
};
