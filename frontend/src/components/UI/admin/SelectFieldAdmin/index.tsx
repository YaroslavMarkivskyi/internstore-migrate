import { FC, ReactNode } from 'react';

import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { SxProps } from '@mui/material';

import CustomMenuItem, { CustomMenuOption } from '../CustomMenuItem';
import InputFieldAdmin, { InputFieldProps } from '../InputFieldAdmin';

import colors from '../../../../constants/colors';

import { Label, PlaceholderWrapper } from './styles';

export interface SelectItem extends CustomMenuOption {
  /** Value to be passed to onChange */
  value: string | number;
  /** Text to be displayed in the option */
  label: string;
}

/** Select field for Admin version of website */
export interface SelectFieldProps extends Omit<InputFieldProps, 'select'> {
  /** Options to display */
  options: SelectItem[];
  /** Component to insert at the start of all options. Does not override the startComponent prop on option item. */
  startComponent?: ReactNode;
  /** Component to insert at the end of all options. Does not override the endComponent prop on option item. */
  endComponent?: ReactNode;
  /** Whether to allow multiple selection or not. */
  multiple?: boolean;
  /** Sx Props to pass to CustomMenuItem */
  menuItemSx?: SxProps;
}

const SelectFieldAdmin: FC<SelectFieldProps> = ({
  options,
  placeholder,
  startComponent,
  endComponent,
  label,
  multiple,
  menuItemSx,
  ...rest
}) => {
  return (
    <InputFieldAdmin
      {...rest}
      select
      label={multiple ? null : label}
      slotProps={{
        ...rest.slotProps,
        select: {
          ...rest.slotProps?.select,
          multiple: multiple,
          MenuProps: {
            sx: {
              '& .MuiList-root': {
                padding: 0,
                overflowY: 'auto',
                maxHeight: 240,
              },
              '& .MuiPaper-root': {
                borderRadius: '10px',
                overflow: 'hidden',
              },
            },
          },
          IconComponent: KeyboardArrowDownIcon,
          displayEmpty: true,
          renderValue: selected => {
            if (selected === null || selected === undefined) {
              return <PlaceholderWrapper>{placeholder}</PlaceholderWrapper>;
            }
            if (selected instanceof Array) {
              return <Label>{label}</Label>;
            }
            const selectedCategory = options.find(
              option => option.value === selected
            );
            return selectedCategory?.label ?? '';
          },
        },
      }}
    >
      {options.map(option => (
        <CustomMenuItem
          key={option.value}
          value={option.value}
          startComponent={option.startComponent ?? startComponent}
          endComponent={option.endComponent ?? endComponent}
          sx={
            multiple
              ? {
                  ...{
                    '&.Mui-selected': {
                      '& .Mui-disabled': {
                        color: colors.secondary.accent100,
                      },
                      backgroundColor: 'transparent',
                      '& .MuiTypography-root': {
                        color: 'inherit',
                      },
                      '&:hover': {
                        backgroundColor: 'inherit',
                      },
                    },
                  },
                  ...menuItemSx,
                }
              : menuItemSx
          }
        >
          {option.label}
        </CustomMenuItem>
      ))}
    </InputFieldAdmin>
  );
};

export default SelectFieldAdmin;
