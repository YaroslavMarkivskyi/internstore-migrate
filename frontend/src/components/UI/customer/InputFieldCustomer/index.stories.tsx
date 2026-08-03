import InputFieldCustomer from './index';

import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta<typeof InputFieldCustomer> = {
  component: InputFieldCustomer,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof InputFieldCustomer>;

export const Base: Story = {};

export const WithLabel: Story = {
  args: {
    label: 'Email',
  },
};

export const FieldRequired: Story = {
  args: {
    ...WithLabel.args,
    required: true,
  },
};

export const Error: Story = {
  args: {
    ...FieldRequired.args,
    error: 'This field is required!',
  },
};

export const ErrorPositionedAbsolute: Story = {
  args: {
    ...Error.args,
    errorPosition: 'absolute',
  },
  render: args => (
    <div>
      <InputFieldCustomer {...args} />
      <InputFieldCustomer {...args} />
    </div>
  ),
};

export const ErrorPositionedDefault: Story = {
  args: {
    ...Error.args,
    errorPosition: 'default',
  },
  render: args => (
    <div>
      <InputFieldCustomer {...args} />
      <InputFieldCustomer {...args} />
    </div>
  ),
};

export const WithPlaceholder: Story = {
  args: {
    placeholder: 'Input your email here...',
  },
};
