import { Outlet } from 'react-router-dom';

import {
  ContentWrapper,
  LayoutContainer,
  MainContentContainer,
  PageContentContainer,
} from '../styles';

import { CartProvider } from '../../hooks/useCart';

import Footer from './components/Footer';
import Navbar from './components/Navbar';

const CustomerLayout = () => {
  return (
    <CartProvider>
      <LayoutContainer>
        <MainContentContainer>
          <Navbar />
          <PageContentContainer>
            <ContentWrapper sx={{ px: { xs: 2, md: '96px' } }}>
              <Outlet />
            </ContentWrapper>
          </PageContentContainer>
          <Footer />
        </MainContentContainer>
      </LayoutContainer>
    </CartProvider>
  );
};

export default CustomerLayout;
