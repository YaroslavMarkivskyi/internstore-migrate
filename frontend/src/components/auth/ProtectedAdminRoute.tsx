import { Navigate, Outlet } from 'react-router-dom';

import { useSelector } from 'react-redux';

import { RootState } from '@store/store';

/**
 * ProtectedAdminRoute - A component that restricts access to admin routes
 *
 * DEVELOPMENT MODE: Currently mocked to always grant access
 *
 * TODO: Implement proper authentication by uncommenting the code below
 * and using the Redux state to check if the user is an admin.
 */
const ProtectedAdminRoute = () => {
  const currentUser = useSelector((state: RootState) => state.auth.currentUser);

  // If no user or user is not admin, redirect to 403 page
  if (!currentUser || !currentUser.is_admin) {
    return <Navigate to="/403" replace />;
  }

  // Otherwise, render the child routes
  return <Outlet />;
};

export default ProtectedAdminRoute;
