import { memo } from 'react';

import Pagination from '@components/UI/common/Pagination';

import { PaginationBox } from './styles';

interface OrdersPaginationProps {
  count: number;
  currentPage: number;
  onPageChange?: (page: number) => void;
}

const OrdersPagination = ({
  count,
  currentPage,
  onPageChange,
}: OrdersPaginationProps) => {
  const handlePageChange = (_: React.ChangeEvent<unknown>, value: number) => {
    if (onPageChange) {
      onPageChange(value);
    }
  };

  return (
    <PaginationBox>
      <Pagination
        count={count}
        page={currentPage}
        onChange={handlePageChange}
      />
    </PaginationBox>
  );
};

export default memo(OrdersPagination);
