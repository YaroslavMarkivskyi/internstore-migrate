import { useState } from 'react';

import SelectedOrderModal from '@pages/Admin/Orders/components/SelectedOrderModal';
import useFilterOrders from '@pages/Admin/Orders/hooks/useFilterOrders';

import { OrderOrderingPositive } from '../../../types/orders/types';

import OrdersFilter from './components/OrdersFilter';
import OrdersPagination from './components/OrdersPagination';
import OrdersTable from './components/OrdersTable';
import { OrdersContainer, OrdersHeader } from './styles';

const AdminOrders = () => {
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const closeModal = () => setSelectedOrderId(null);

  const {
    orders,
    isLoading,
    count,
    setPage,
    page,
    deleteFilter,
    setFilters,
    limit,
    ordering,
    status,
    archived,
    date,
  } = useFilterOrders();

  const handleChangeOrdering = (newOrdering: OrderOrderingPositive) => {
    if (ordering === newOrdering) {
      setFilters({ ordering: `-${newOrdering}` });
    } else {
      setFilters({ ordering: newOrdering });
    }
  };

  return (
    <OrdersContainer>
      <OrdersHeader variant="h4">Orders</OrdersHeader>
      <OrdersFilter
        setFilters={setFilters}
        deleteFilter={deleteFilter}
        status={status}
        archived={archived}
        date={date}
      />
      <OrdersTable
        orders={orders}
        setOrdering={handleChangeOrdering}
        isLoading={isLoading}
        onOrderSelected={setSelectedOrderId}
      />
      <OrdersPagination
        count={Math.ceil(count / limit)}
        currentPage={page}
        onPageChange={setPage}
      />
      <SelectedOrderModal
        open={selectedOrderId !== null}
        onClose={closeModal}
        selectedOrderId={selectedOrderId}
      />
    </OrdersContainer>
  );
};

export default AdminOrders;
