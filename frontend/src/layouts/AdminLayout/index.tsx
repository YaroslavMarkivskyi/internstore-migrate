import { Outlet } from 'react-router-dom';

import {
  ContentWrapper,
  LayoutContainer,
  MainContentContainer,
  PageContentContainer,
} from '../styles';

import AdminNavbar from './components/AdminNavbar';
import AdminSidebar from './components/AdminSidebar';

const AdminLayout = () => {
  return (
    <LayoutContainer>
      <AdminSidebar />
      <MainContentContainer>
        <AdminNavbar />
        <PageContentContainer>
          <ContentWrapper>
            <Outlet />
          </ContentWrapper>
        </PageContentContainer>
      </MainContentContainer>
    </LayoutContainer>
  );
};

export default AdminLayout;
