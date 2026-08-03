import React, { useCallback, useEffect, useRef, useState } from 'react';

import { useLocation, useNavigate } from 'react-router';

import { useSelector } from 'react-redux';

import { AppBar, Box, Button, Toolbar } from '@mui/material';

import { AuthModal } from '@components/auth/CustomerAuthModal';
import { SearchBar } from '@components/SearchBar';
import Logo from '@components/UI/common/Logo';
import SimplePopover from '@components/UI/common/SimplePopover';
import UserModal from '@components/UserModal';
import colors from '@constants/colors';
import Cart from '@layouts/CustomerLayout/components/Cart';
import { RootState } from '@store/store';
import { isAdmin } from '@utils/isAdmin';

import { ProfileIcon, StyledIconButton } from './styles';

const Navbar: React.FC = () => {
  const anchorRef = useRef<HTMLButtonElement>(null);
  const currentUser = useSelector((state: RootState) => state.auth.currentUser);
  const [showAdminButton, setShowAdminButton] = useState<boolean>(false);
  const [isCartOpen, setIsCartOpen] = useState(false);

  const toggleCartOpen = useCallback(() => {
    setIsCartOpen(prev => !prev);
  }, []);

  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Show admin button if user is admin
    setShowAdminButton(isAdmin());
  }, [location.pathname, currentUser]);

  return (
    <>
      <AppBar position="static" color="transparent" elevation={0}>
        <Toolbar
          sx={{
            px: { xs: 2, md: '80px' },
            display: 'grid',
            gridTemplateColumns: '1fr auto 1fr',
            alignItems: 'center',
          }}
        >
          {/* Logo section - left aligned */}
          <Box sx={{ my: 3, justifySelf: 'start' }}>
            <Logo onClick={() => navigate('/')} />
          </Box>

          {/* Search bar - always centered regardless of right section content */}
          <Box sx={{ justifySelf: 'center' }}>
            <SearchBar area="customer" />
          </Box>

          {/* User controls and admin button - right aligned */}
          <Box
            display="flex"
            flexDirection="row"
            alignItems="center"
            gap={2}
            justifySelf="end"
          >
            {showAdminButton && (
              <Button
                variant="outlined"
                onClick={() => navigate('/admin/products')}
                sx={{
                  border: `1px solid ${colors.secondary.accent100}`,
                  borderRadius: '5px',
                  color: colors.text100,
                  fontSize: '16px',
                  textTransform: 'none',
                  verticalAlign: 'middle',
                  '&:hover': {
                    border: `1px solid ${colors.secondary.accent200}`,
                    backgroundColor: 'rgba(61, 49, 142, 0.04)',
                  },
                }}
              >
                Admin Panel
              </Button>
            )}
            <SimplePopover
              trigger={
                <StyledIconButton ref={anchorRef}>
                  <ProfileIcon />
                </StyledIconButton>
              }
              anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'right',
              }}
              transformOrigin={{
                vertical: -20,
                horizontal: 'right',
              }}
              slotProps={{ paper: { sx: { borderRadius: '10px' } } }}
            >
              {currentUser ? <UserModal /> : <AuthModal />}
            </SimplePopover>
            <StyledIconButton onClick={toggleCartOpen}>
              <Cart open={isCartOpen} onClose={toggleCartOpen} />
            </StyledIconButton>
          </Box>
        </Toolbar>
      </AppBar>
    </>
  );
};

export default Navbar;
