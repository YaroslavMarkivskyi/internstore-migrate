import Logo from './index';

import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta<typeof Logo> = {
  component: Logo,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof Logo>;

export const Customer: Story = {};

export const Admin: Story = {
  args: {
    isAdmin: true,
  },
};
