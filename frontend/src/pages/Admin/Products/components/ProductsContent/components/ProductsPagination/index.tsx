import { memo } from 'react';

import Pagination from '@components/UI/common/Pagination';

import { PaginationBox } from './styles';

interface ProductsPaginationProps {
  count: number;
  currentPage: number;
  onPageChange?: (page: number) => void;
}

const ProductsPagination = ({
  count,
  currentPage,
  onPageChange,
}: ProductsPaginationProps) => {
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

export default memo(ProductsPagination);
