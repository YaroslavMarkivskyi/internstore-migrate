import { Outlet, Route, Routes } from 'react-router-dom';

import AdminLayout from '@layouts/AdminLayout';
import CustomerLayout from '@layouts/CustomerLayout';
import AddProduct from '@pages/Admin/AddProduct';
import EditProduct from '@pages/Admin/EditProduct';
import AdminOrders from '@pages/Admin/Orders';
import AdminProductsSearch from '@pages/Admin/ProductsSearch';
import CategoryMenu from '@pages/Customer/CategoryMenu';
import CategoryPage from '@pages/Customer/CategoryPage';
import Checkout from '@pages/Customer/Checkout';
import Homepage from '@pages/Customer/Homepage';
import CustomerOrders from '@pages/Customer/Orders';
import ProductPage from '@pages/Customer/ProductPage';
import CustomerProfile from '@pages/Customer/Profile';
import Page403 from '@pages/Errors/403';
import Page404 from '@pages/Errors/404';
import { selectAccessToken, selectCurrentUser } from '@store/reducers/auth';
import { useSelector } from '@store/store';

import ProtectedAdminRoute from './components/auth/ProtectedAdminRoute';
import { useNotifications } from './hooks/useNotifications';
import AdminCategories from './pages/Admin/Categories';
import AdminDashboard from './pages/Admin/Dashboard';
import AdminProducts from './pages/Admin/Products';
import AdminStocks from './pages/Admin/Stocks';
import AdminLogin from './pages/AdminLogin/';

function App() {
  const accessToken = useSelector(selectAccessToken);
  const currentUser = useSelector(selectCurrentUser);

  useNotifications({
    accessToken,
    isAdmin: currentUser?.is_admin || false,
    // Disabled: this hook opens an SSE connection to
    // `${SERVER_URL}notifications/live/`, which has no Gateway route --
    // internstore-migrate's Notifications service is a pure Kafka
    // consumer + SMTP sender by design (see
    // internstore-migrate/docs/EVENT_BROKER.md and
    // internstore-migrate/services/notifications/README.md), not a
    // synchronous HTTP service. Every admin session was retrying this
    // against a 405 5 times on load. Re-enable only once/if a real
    // HTTP/SSE endpoint exists on that service.
    enabled: false,
  });

  return (
    <Routes>
      <Route path="/" element={<CustomerLayout />}>
        <Route element={<CategoryMenu />}>
          <Route index element={<Homepage />} />
          <Route path="categories/:categoryId" element={<CategoryPage />} />
          <Route
            path="products/:id"
            element={<ProductPage area={'customer'} />}
          />
        </Route>
        <Route path="profile" element={<CustomerProfile />}>
          <Route path="orders" element={<CustomerOrders />} />
        </Route>
        <Route path="checkout" element={<Checkout />} />
      </Route>

      {/* Admin product preview route - uses customer layout but requires admin access */}
      <Route path="/admin/products/preview" element={<ProtectedAdminRoute />}>
        <Route element={<CustomerLayout />}>
          <Route element={<CategoryMenu />}>
            <Route path=":id" element={<ProductPage area={'admin'} />} />
          </Route>
        </Route>
      </Route>

      <Route path="/admin" element={<ProtectedAdminRoute />}>
        <Route element={<AdminLayout />}>
          <Route path="dashboard" element={<AdminDashboard />} />
          <Route path="products" element={<AdminProducts />} />
          <Route path="products/search" element={<AdminProductsSearch />} />
          <Route path="categories/*" element={<AdminCategories />} />
          <Route path="products" element={<Outlet />}>
            <Route index element={<AdminProducts />} />
            <Route path="add" element={<AddProduct />} />
            <Route path="edit/:productId" element={<EditProduct />} />
            <Route path="search" element={<AdminProductsSearch />} />
          </Route>
          <Route path="stocks" element={<AdminStocks />} />
          <Route path="stocks/:stockId" element={<AdminStocks />} />
          <Route path="orders" element={<AdminOrders />} />
        </Route>
      </Route>

      <Route path="/admin/login" element={<AdminLogin />} />
      <Route path="/403" element={<Page403 />} />
      <Route path="*" element={<Page404 />} />
    </Routes>
  );
}

export default App;
