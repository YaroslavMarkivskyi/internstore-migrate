import { FC, ReactNode } from 'react';

import SwapVertIcon from '@mui/icons-material/SwapVert';
import { IconButton, TableCell } from '@mui/material';

import { Wrapper } from '@pages/Admin/Orders/components/SelectedOrderModal/SortCell/styles';

interface SortCellProps {
  children?: ReactNode;
  applyOrdering: () => void;
  isLoading?: boolean;
}

const SortCell: FC<SortCellProps> = ({
  children,
  applyOrdering,
  isLoading,
}) => {
  return (
    <TableCell>
      <Wrapper>
        {children}
        <IconButton
          onClick={applyOrdering}
          disabled={isLoading}
          aria-label={`Sort by ${children}`}
        >
          <SwapVertIcon />
        </IconButton>
      </Wrapper>
    </TableCell>
  );
};

export default SortCell;
