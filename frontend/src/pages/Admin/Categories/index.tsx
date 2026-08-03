import { Route, Routes } from 'react-router-dom';

import CategoriesContent from './components/CategoriesContent';

const AdminCategories = () => {
  return (
    <Routes>
      <Route index element={<CategoriesContent />} />
      <Route path=":categoryId" element={<CategoriesContent />} />
    </Routes>
  );
};

export default AdminCategories;
