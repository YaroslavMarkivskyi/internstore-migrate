import { forwardRef } from 'react';

import ArrowBackIosIcon from '@mui/icons-material/ArrowBackIos';
import ArrowForwardIosIcon from '@mui/icons-material/ArrowForwardIos';
import {
  Pagination as PaginationBase,
  PaginationItem,
  PaginationProps,
} from '@mui/material';

const Pagination = forwardRef<HTMLDivElement, PaginationProps>((props, ref) => {
  return props.count && props.count > 1 ? (
    <PaginationBase
      ref={ref}
      {...props}
      shape="rounded"
      renderItem={item => (
        <PaginationItem
          slots={{ previous: ArrowBackIosIcon, next: ArrowForwardIosIcon }}
          {...item}
        />
      )}
    />
  ) : null;
});

export default Pagination;
