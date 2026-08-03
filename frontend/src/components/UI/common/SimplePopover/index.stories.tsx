import FilterAltOutlinedIcon from '@mui/icons-material/FilterAltOutlined';
import { Box } from '@mui/material';

import RangeSlider from '../RangeSlider';

import colors from '../../../../constants/colors';
import ButtonAdmin from '../../admin/ButtonAdmin';
import ButtonCustomer from '../../customer/ButtonCustomer';

import SimplePopover, { PopoverChildProps } from './index';

import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta<typeof SimplePopover> = {
  component: SimplePopover,
  tags: ['autodocs'],
  args: {
    trigger: <ButtonAdmin>Open Me!</ButtonAdmin>,
  },
};

export default meta;
type Story = StoryObj<typeof SimplePopover>;

export const Base: Story = {
  args: {
    children: <Box>Hello I am popover!</Box>,
  },
};

export const PriceFilter: Story = {
  args: {
    trigger: (
      <ButtonCustomer
        startIcon={<FilterAltOutlinedIcon />}
        sx={{
          '&.MuiButton-outlined': {
            border: `1px solid ${colors.backgroundDisabled}`,
          },
        }}
      >
        Filter by price
      </ButtonCustomer>
    ),
    children: (
      <Box sx={{ p: 3, width: 500 }}>
        <RangeSlider min={0} max={100} />
      </Box>
    ),
    anchorOrigin: {
      vertical: 'bottom',
      horizontal: 'center',
    },
    transformOrigin: {
      vertical: 'top',
      horizontal: 'center',
    },
  },
};

export const ClosingFromInsideOfChildren: Story = {
  args: {
    ...PriceFilter.args,
  },
  render: args => {
    const ClosingButton = ({ onRequestClose }: PopoverChildProps) => (
      <Box sx={{ p: 3, width: 500 }}>
        <ButtonAdmin onClick={onRequestClose}>
          It closes this popover
        </ButtonAdmin>
      </Box>
    );

    return <SimplePopover {...args} children={<ClosingButton />} />;
  },
};
