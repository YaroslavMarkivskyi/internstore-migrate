import { Stack } from '@mui/material';
import { fn } from '@storybook/test';

import Tag from './index';

import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta<typeof Tag> = {
  component: Tag,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof Tag>;

export const Base: Story = {
  args: {
    children: 'Protein Bar',
    onCloseClick: fn(),
  },
};

export const MultipleTags: Story = {
  render: () => (
    <Stack
      direction="row"
      maxWidth={730}
      flexWrap="wrap"
      rowGap="30px"
      columnGap="15px"
    >
      <Tag>Protein Bar</Tag>
      <Tag>From $1.25 to $20.00</Tag>
      <Tag>From 15 to 200</Tag>
      <Tag>Stock 1</Tag>
      <Tag>Published</Tag>
      <Tag>From 05/04/2023 to 05/10/2023</Tag>
      <Tag>New</Tag>
    </Stack>
  ),
};
