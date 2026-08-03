import { CircularProgress } from '@mui/material';

import Pagination from '@components/UI/common/Pagination';
import Order from '@pages/Customer/Orders/components/Order';
import useOrders from '@pages/Customer/Orders/hooks/useOrders';
import {
  ListContainer,
  NothingFoundText,
  Title,
  Wrapper,
} from '@pages/Customer/Orders/styles';

const Orders = () => {
  const { orders, setPage, count, isLoading, page, limit } = useOrders(8);

  return (
    <Wrapper>
      <Title>Orders</Title>
      {isLoading ? (
        <CircularProgress sx={{ m: 'auto' }} />
      ) : (
        <ListContainer>
          {orders.map(order => (
            <Order key={order.id} order={order} />
          ))}
          {orders.length === 0 && (
            <NothingFoundText>There is nothing yet..</NothingFoundText>
          )}
        </ListContainer>
      )}
      <Pagination
        sx={{ mx: 'auto' }}
        count={Math.ceil(count / limit)}
        page={page}
        onChange={(_e, p) => setPage(p)}
      />
    </Wrapper>
  );
};

export default Orders;
