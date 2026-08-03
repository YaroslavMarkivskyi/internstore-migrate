import { OrderStatus } from '../../../../../../types/orders/types';

export interface Order {
  id: number;
  customerName: string;
  date: string;
  status: OrderStatus;
  price: string;
  phone: string;
}

export const orders: Order[] = [
  {
    id: 1,
    customerName: 'John Black',
    date: '04/13/2023',
    status: 'new',
    price: '$500.00',
    phone: '+1 202-918-2132',
  },
  {
    id: 2,
    customerName: 'Sandra Gilmore',
    date: '04/12/2023',
    status: 'new',
    price: '$570.00',
    phone: '+1 229-485-4504',
  },
  {
    id: 3,
    customerName: 'Emil Watkins',
    date: '04/12/2023',
    status: 'new',
    price: '$430.00',
    phone: '+1 215-389-4341',
  },
  {
    id: 4,
    customerName: 'Susan Hartley',
    date: '04/11/2023',
    status: 'new',
    price: '$205.00',
    phone: '+1 505-646-4916',
  },
  {
    id: 5,
    customerName: 'Nate Marsh',
    date: '04/11/2023',
    status: 'new',
    price: '$102.00',
    phone: '+1 505-644-8986',
  },
];
