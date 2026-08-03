import { store } from '@store/store';

/**
 * Utility function to check if the current user is an admin
 * @returns {boolean} True if the user is an admin, false otherwise
 */
export const isAdmin = (): boolean => {
  const state = store.getState();
  const currentUser = state.auth.currentUser;

  // Return false if no user is logged in
  if (!currentUser) {
    return false;
  }

  return currentUser.is_admin === true;
};

/**
 * A React hook that can be used in components to check admin status
 * @returns {boolean} True if the user is an admin, false otherwise
 */
export const useIsAdmin = (): boolean => {
  return isAdmin();
};
