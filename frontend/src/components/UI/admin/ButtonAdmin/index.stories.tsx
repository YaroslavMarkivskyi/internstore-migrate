import AddIcon from '@mui/icons-material/Add';

import ButtonAdmin from './index';

import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta<typeof ButtonAdmin> = {
  component: ButtonAdmin,
  tags: ['autodocs'],
  args: {
    children: 'Text',
  },
};

export default meta;
type Story = StoryObj<typeof ButtonAdmin>;

export const Text: Story = {
  args: {
    variant: 'text',
  },
};

export const TextDisabled: Story = {
  args: {
    ...Text.args,
    disabled: true,
  },
};

export const Outlined: Story = {
  args: {
    variant: 'outlined',
  },
};

export const Contained: Story = {
  args: {
    variant: 'contained',
  },
};

export const DisabledContained: Story = {
  args: {
    disabled: true,
    ...Contained.args,
  },
};

export const DisabledOutlined: Story = {
  args: {
    disabled: true,
    ...Outlined.args,
  },
};

export const WithIcon: Story = {
  args: {
    ...Contained.args,
    endIcon: <AddIcon sx={{ ml: 1.5 }} />,
    sx: {
      px: 4,
    },
    children: 'Add a product',
  },
  render: ({ sx, ...args }) => (
    <div
      style={{
        display: 'flex',
        flexDirection: 'row',
        columnGap: '30px',
        alignItems: 'center',
      }}
    >
      <ButtonAdmin {...args} sx={sx} />
      <ButtonAdmin {...args} sx={sx} {...Outlined.args} />
      <ButtonAdmin {...args} variant="text" />
    </div>
  ),
};
