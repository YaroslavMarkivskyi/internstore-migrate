import { Box, Popover as MuiPopover, styled, Typography } from '@mui/material';

import colors from '@constants/colors';

export const FilterContainer = styled(Box)({
  marginBottom: '24px',
  width: '100%',
  boxSizing: 'border-box',
});

export const FiltersRow = styled(Box)({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: 16,
});

export const FiltersGroup = styled(Box)({
  display: 'flex',
  gap: 16,
});

export const FilterBox = styled(Box)({
  minWidth: 180,
});

export const PublishFilterBox = styled(Box)({
  minWidth: 220,
});

export const AddProductButtonStyle = {
  px: 4,
};

export const SelectFieldStyle = {
  '& .MuiOutlinedInput-root': {
    borderRadius: '8px',
    height: '56px',
    backgroundColor: '#FFFFFF',
  },
  '& .MuiSelect-select': {
    color: colors.text100,
    fontWeight: 500,
  },
  '& .MuiPaper-root': {
    maxHeight: '300px',
  },
};

export const FilterTriggerBox = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  cursor: 'pointer',
  border: `1px solid #E0E0E0`,
  borderRadius: '8px',
  padding: '0 16px',
  height: '56px',
  boxSizing: 'border-box',
  backgroundColor: '#FFFFFF',
  '&:hover': {
    borderColor: '#BCBCBC',
  },
});

export const FilterLabel = styled(Typography)({
  flexGrow: 1,
  color: colors.text100,
  fontWeight: 500,
});

export const ArrowIcon = styled(Box)({
  color: '#666',
  display: 'flex',
  alignItems: 'center',
});

export const PopoverAnchorOrigin = {
  vertical: 'bottom' as const,
  horizontal: 'left' as const,
};

export const PopoverTransformOrigin = {
  vertical: 'top' as const,
  horizontal: 'left' as const,
};

export const StyledPopover = styled(MuiPopover)({
  '& .MuiPaper-root': {
    marginTop: 8,
    padding: 16,
    width: 400,
    boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.1)',
    borderRadius: '8px',
    backgroundColor: '#FFFFFF',
  },
});

export const TagsContainer = styled(Box)({
  minHeight: 36,
});

export const TagsWrapper = styled(Box)({
  display: 'flex',
  flexWrap: 'wrap',
  gap: 4,
});
