import { useState } from 'react';

import AccountCircleOutlinedIcon from '@mui/icons-material/AccountCircleOutlined';
import CheckOutlinedIcon from '@mui/icons-material/CheckOutlined';
import LogoutOutlinedIcon from '@mui/icons-material/LogoutOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import SortOutlinedIcon from '@mui/icons-material/SortOutlined';
import { IconButton } from '@mui/material';
import { fn } from '@storybook/test';

import colors from '../../../../constants/colors';
import ButtonAdmin from '../../admin/ButtonAdmin';
import ButtonCustomer from '../../customer/ButtonCustomer';

import MenuPopup from './index';

import type { Meta, StoryObj } from '@storybook/react';

const meta: Meta<typeof MenuPopup> = {
  component: MenuPopup,
  tags: ['autodocs'],
  args: {
    children: <ButtonAdmin variant="contained">Click Me</ButtonAdmin>,
  },
};

export default meta;
type Story = StoryObj<typeof MenuPopup>;

export const Base: Story = {
  args: {
    options: [{ label: 'Option', onClick: fn() }],
  },
};

export const WithIcons: Story = {
  args: {
    options: [
      {
        label: 'My account',
        onClick: fn(),
        startComponent: <AccountCircleOutlinedIcon />,
      },
      {
        label: 'Log out',
        onClick: fn(),
        startComponent: <LogoutOutlinedIcon />,
      },
    ],
  },
};

export const CustomPositioning: Story = {
  args: {
    ...WithIcons.args,
    anchorOrigin: {
      vertical: 'top',
      horizontal: 'right',
    },
    transformOrigin: {
      vertical: 'bottom',
      horizontal: 'right',
    },
  },
};

export const MarginOnOpened: Story = {
  args: {
    ...WithIcons.args,
    transformOrigin: {
      horizontal: 'left',
      vertical: -20,
    },
  },
};

export const SortByPrice: Story = {
  render: () => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const [title, setTitle] = useState('Sort by price');

    const ascendingTitle = 'Lowest to Highest';
    const descendingTitle = 'Highest to Lowest';

    const checkedComponent = (
      <CheckOutlinedIcon fill={colors.secondary.accent100} sx={{ ml: 1 }} />
    );

    const options = [
      {
        endComponent: title === ascendingTitle && checkedComponent,
        label: ascendingTitle,
        onClick: () => setTitle(ascendingTitle),
      },
      {
        endComponent: title === descendingTitle && checkedComponent,
        label: descendingTitle,
        onClick: () => setTitle(descendingTitle),
      },
    ];

    return (
      <MenuPopup options={options}>
        <ButtonCustomer
          startIcon={<SortOutlinedIcon />}
          variant={'outlined'}
          sx={{
            '&.MuiButton-outlined': {
              border: `1px solid ${colors.backgroundDisabled}`,
            },
          }}
        >
          {title}
        </ButtonCustomer>
      </MenuPopup>
    );
  },
};

export const CustomTrigger: Story = {
  args: {
    ...WithIcons.args,
    children: (
      <IconButton>
        <MoreVertIcon />
      </IconButton>
    ),
  },
};
