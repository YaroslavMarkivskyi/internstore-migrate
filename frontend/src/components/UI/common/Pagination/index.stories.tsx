import { fn } from '@storybook/test';

import Pagination from './index';

import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta<typeof Pagination> = {
  component: Pagination,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof Pagination>;

export const Base: Story = {
  args: {
    page: 1,
    count: 3,
    onChange: fn(),
  },
};

export const ManyPages: Story = {
  args: {
    page: 50,
    count: 100,
    onChange: fn(),
  },
};
