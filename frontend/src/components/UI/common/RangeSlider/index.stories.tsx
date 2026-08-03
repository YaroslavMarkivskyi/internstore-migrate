import { useState } from 'react';

import { Paper } from '@mui/material';
import { Meta, StoryObj } from '@storybook/react';

import RangeSlider from './index';

const meta: Meta<typeof RangeSlider> = {
  component: RangeSlider,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof RangeSlider>;

// Basic story
export const Default: Story = {
  args: {
    min: 0,
    max: 100,
    defaultValue: [25, 75],
  },
  render: args => (
    <Paper sx={{ p: 3, width: 500 }}>
      <RangeSlider {...args} />
    </Paper>
  ),
};

// Price range example
export const PriceRange: Story = {
  args: {
    min: 0,
    max: 100,
    defaultValue: [0, 100],
    prefix: '$',
  },
  render: args => (
    <Paper sx={{ p: 3, width: 500 }}>
      <RangeSlider {...args} />
    </Paper>
  ),
};

// Interactive example with state
export const InteractiveExample: Story = {
  render: () => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const [value, setValue] = useState<[number, number]>([0, 100]);

    const handleChange = (newValue: [number, number]) => {
      setValue(newValue);
      console.log('Range changed:', newValue);
    };

    return (
      <Paper sx={{ p: 3, width: 500 }}>
        <RangeSlider
          min={0}
          max={100}
          defaultValue={value}
          onChange={handleChange}
          prefix="$"
        />
      </Paper>
    );
  },
};

// Custom track color
export const CustomTrackColor: Story = {
  args: {
    min: 0,
    max: 100,
    defaultValue: [20, 80],
    trackColor: '#3D318E',
  },
  render: args => (
    <Paper sx={{ p: 3, width: 500 }}>
      <RangeSlider {...args} />
    </Paper>
  ),
};

// Disabled state
export const Disabled: Story = {
  args: {
    min: 0,
    max: 100,
    defaultValue: [30, 70],
    disabled: true,
  },
  render: args => (
    <Paper sx={{ p: 3, width: 500 }}>
      <RangeSlider {...args} />
    </Paper>
  ),
};

// Example matching design image
export const DesignMatch: Story = {
  args: {
    min: 0,
    max: 100,
    defaultValue: [0, 100],
    prefix: '$',
  },
  render: args => (
    <Paper
      sx={{
        p: 3,
        width: 500,
        border: '1px solid #8b5cf6',
        borderRadius: '8px',
      }}
    >
      <RangeSlider {...args} />
    </Paper>
  ),
};
