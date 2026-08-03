import { Stack } from '@mui/material';

import OrderStatus from './index';

import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta<typeof OrderStatus> = {
  component: OrderStatus,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof OrderStatus>;

export const Base: Story = {
  args: {
    status: 'new',
  },
};

export const AllStatuses: Story = {
  render: () => (
    <Stack direction="row" columnGap="20px">
      <OrderStatus status="new" />
      <OrderStatus status="pending" />
      <OrderStatus status="paid" />
      <OrderStatus status="cancelled" />
      <OrderStatus status="rejected" />
      <OrderStatus status="done" />
    </Stack>
  ),
};
