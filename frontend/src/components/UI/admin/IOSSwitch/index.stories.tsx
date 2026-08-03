import { Box, FormControlLabel, Typography } from '@mui/material';
import { Meta, StoryObj } from '@storybook/react';

import IOSSwitch from './index';

const meta: Meta<typeof IOSSwitch> = {
  component: IOSSwitch,
  tags: ['autodocs'],
  argTypes: {
    checked: { control: 'boolean' },
    disabled: { control: 'boolean' },
  },
};

export default meta;
type Story = StoryObj<typeof IOSSwitch>;

// Basic story with the switch rendered directly
export const Default: Story = {
  args: {
    checked: false,
  },
};

// Example with the switch checked
export const Checked: Story = {
  args: {
    checked: true,
  },
};

// Example with the switch disabled
export const Disabled: Story = {
  args: {
    checked: false,
    disabled: true,
  },
};

// Example with the switch in a FormControlLabel (as used in the products table)
export const WithLabel: Story = {
  render: args => (
    <FormControlLabel control={<IOSSwitch {...args} />} label="Published" />
  ),
  args: {
    checked: true,
  },
};

// Example showing both states side by side
export const BothStates: Story = {
  render: () => (
    <Box sx={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      <Box
        sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}
      >
        <IOSSwitch checked={false} />
        <Typography variant="body2" sx={{ mt: 1 }}>
          Unpublished
        </Typography>
      </Box>
      <Box
        sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}
      >
        <IOSSwitch checked={true} />
        <Typography variant="body2" sx={{ mt: 1 }}>
          Published
        </Typography>
      </Box>
    </Box>
  ),
};
