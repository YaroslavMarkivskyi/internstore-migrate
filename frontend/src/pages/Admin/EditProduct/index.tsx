import { useParams } from 'react-router';

import ProductForm from '@components/ProductForm';
import { ProductFormDataOutput } from '@components/ProductForm/schema';
import { editProduct } from '@services/http/admin/products';

const EditProduct = () => {
  const { productId } = useParams();

  const onSubmit = async (data: ProductFormDataOutput) => {
    await editProduct(productId as string, data);
  };

  return <ProductForm onSubmit={onSubmit} productId={productId} />;
};

export default EditProduct;
