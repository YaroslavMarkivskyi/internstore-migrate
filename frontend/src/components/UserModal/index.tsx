import React, { useState } from 'react';

import { useLocation, useNavigate } from 'react-router';

import AccountCircleOutlinedIcon from '@mui/icons-material/AccountCircleOutlined';
import LogoutOutlinedIcon from '@mui/icons-material/LogoutOutlined';
import { Box } from '@mui/material';

import { logout } from '@services/http/public/auth';
import {
  clearCredentials,
  selectCurrentUser,
  selectRefreshToken,
} from '@store/reducers/auth';
import { useDispatch, useSelector } from '@store/store';
import { hasUserActivity } from '@utils/activityDetection';
import showToast from '@utils/showToast';

import CustomMenuItem from '../UI/admin/CustomMenuItem';

import LogoutConfirmationModal from './components/LogoutConfirmationModal';

const UserModal: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch();
  const refreshToken = useSelector(selectRefreshToken);
  const currentUser = useSelector(selectCurrentUser);

  const [showLogoutConfirmation, setShowLogoutConfirmation] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleAccountClick = () => {
    navigate('/profile/orders');
  };

  const handleLogoutClick = async () => {
    // Check for user activity before proceeding
    const hasActivity = hasUserActivity(location.pathname);

    if (hasActivity) {
      setShowLogoutConfirmation(true);
      return;
    }

    // Proceed with normal logout if no activity
    await performLogout();
  };

  const performLogout = async () => {
    if (!refreshToken || !currentUser) return;

    setIsLoggingOut(true);

    try {
      // Navigate first, then perform logout
      if (currentUser.is_admin) {
        navigate('/admin/login/');
      } else {
        navigate('/');
      }

      await logout({ refresh: refreshToken });
      dispatch(clearCredentials());

      showToast({
        message: 'Successfully signed out.',
        type: 'success',
      });
    } catch {
      showToast({
        message: 'Error during logout, please try again.',
        type: 'error',
      });
    } finally {
      setIsLoggingOut(false);
      setShowLogoutConfirmation(false);
    }
  };

  const handleLogoutConfirm = async () => {
    await performLogout();
  };

  const handleLogoutCancel = () => {
    setShowLogoutConfirmation(false);
  };

  return (
    <>
      <Box>
        <CustomMenuItem
          startComponent={<AccountCircleOutlinedIcon />}
          onClick={handleAccountClick}
        >
          My profile
        </CustomMenuItem>
        <CustomMenuItem
          startComponent={<LogoutOutlinedIcon />}
          onClick={handleLogoutClick}
        >
          Log out
        </CustomMenuItem>
      </Box>

      <LogoutConfirmationModal
        isOpen={showLogoutConfirmation}
        onConfirm={handleLogoutConfirm}
        onCancel={handleLogoutCancel}
        isLoading={isLoggingOut}
      />
    </>
  );
};

export default UserModal;
