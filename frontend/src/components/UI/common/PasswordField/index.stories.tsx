import PasswordField from './index';

import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta<typeof PasswordField> = {
  component: PasswordField,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof PasswordField>;

export const Base: Story = {};

export const Error: Story = {
  args: {
    error: 'This field is required!',
  },
};

export const WithPlaceholder: Story = {
  args: {
    placeholder: 'Input your email here...',
  },
};
