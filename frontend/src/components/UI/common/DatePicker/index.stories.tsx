import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { fn } from '@storybook/test';

import SimplePopover from '../SimplePopover';

import ButtonAdmin from '../../admin/ButtonAdmin';

import DatePicker from './index';

import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta<typeof DatePicker> = {
  component: DatePicker,
  tags: ['autodocs'],
  args: {
    onChange: fn(),
  },
};

export default meta;
type Story = StoryObj<typeof DatePicker>;

export const Base: Story = {};

export const InsidePopover: Story = {
  render: () => (
    <SimplePopover
      sx={{
        '& .MuiPaper-root': {
          borderRadius: '10px',
        },
      }}
      trigger={
        <ButtonAdmin endIcon={<KeyboardArrowDownIcon />}>Date</ButtonAdmin>
      }
    >
      <DatePicker onChange={fn()} />
    </SimplePopover>
  ),
};
