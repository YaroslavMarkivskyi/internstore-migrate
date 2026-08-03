import VerifiedIcon from '@mui/icons-material/Verified';
import { Checkbox, Radio } from '@mui/material';
import { fn } from '@storybook/test';

import OrderStatus from '../../common/OrderStatus';

import SelectFieldAdmin from './index';

import type { Meta, StoryObj } from '@storybook/react';

const options = [
  { value: 1, label: 'Protein' },
  { value: 2, label: 'Steroids' },
  { value: 3, label: 'Gainer' },
  { value: 4, label: 'Creatine' },
  { value: 5, label: 'Vitamins' },
  { value: 6, label: 'Gear' },
];

const meta: Meta<typeof SelectFieldAdmin> = {
  component: SelectFieldAdmin,
  tags: ['autodocs'],
  args: {
    options: options,
    onChange: fn(),
  },
  decorators: [
    Story => (
      <div style={{ width: 200 }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof SelectFieldAdmin>;

export const Base: Story = {};

export const WithLabel: Story = {
  args: {
    label: 'Category',
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
      <SelectFieldAdmin {...args} />
      <SelectFieldAdmin {...args} />
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
      <SelectFieldAdmin {...args} />
      <SelectFieldAdmin {...args} />
    </div>
  ),
};

export const WithPlaceholder: Story = {
  args: {
    placeholder: 'Select category',
  },
};

export const WithIcons: Story = {
  args: {
    startComponent: <VerifiedIcon />,
    endComponent: <Radio size="small" />,
  },
};

export const MultipleSelect: Story = {
  args: {
    endComponent: <Checkbox />,
    defaultValue: [],
    multiple: true,
    label: 'Category',
  },
};

export const MultipleSelectWithCustomIcons: Story = {
  args: {
    endComponent: <Checkbox />,
    defaultValue: [],
    multiple: true,
    label: 'Category',
    options: [
      {
        value: 1,
        label: '',
        startComponent: <OrderStatus status={'new'} />,
      },
      {
        value: 2,
        label: '',
        startComponent: <OrderStatus status={'pending'} />,
      },
      {
        value: 3,
        label: '',
        startComponent: <OrderStatus status={'paid'} />,
      },
      {
        value: 4,
        label: '',
        startComponent: <OrderStatus status={'cancelled'} />,
      },
      {
        value: 5,
        label: '',
        startComponent: <OrderStatus status={'rejected'} />,
      },
      {
        value: 6,
        label: '',
        startComponent: <OrderStatus status={'done'} />,
      },
    ],
  },
};
