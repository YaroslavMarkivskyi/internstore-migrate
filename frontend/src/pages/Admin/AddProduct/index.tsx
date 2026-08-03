import { useSearchParams } from 'react-router-dom';

import ProductForm from '@components/ProductForm';
import { ProductFormDataOutput } from '@components/ProductForm/schema';
import { addProduct } from '@services/http/admin/products';

const AddProduct = () => {
  const [searchParams] = useSearchParams();
  const duplicateFromProductId = searchParams.get('duplicateId');
  const isDuplicate = !!duplicateFromProductId;

  const onSubmit = async (data: ProductFormDataOutput) => {
    await addProduct(data);
  };

  return (
    <ProductForm
      onSubmit={onSubmit}
      productId={duplicateFromProductId ?? undefined}
      isDuplicate={isDuplicate}
    />
  );
};

export default AddProduct;
