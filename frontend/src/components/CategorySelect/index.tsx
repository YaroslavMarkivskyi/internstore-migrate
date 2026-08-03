import { forwardRef, useEffect, useState } from 'react';

import SelectFieldAdmin, {
  SelectFieldProps,
  SelectItem,
} from '@components/UI/admin/SelectFieldAdmin';
import { getCategories } from '@services/http/admin/categories';
import { setCategories } from '@store/reducers/category';
import { useDispatch } from '@store/store';

type CategorySelectProps = Omit<SelectFieldProps, 'options'>;

const CategorySelect = forwardRef<HTMLInputElement, CategorySelectProps>(
  (props, ref) => {
    const [options, setOptions] = useState<SelectItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const dispatch = useDispatch();

    const getOptions = async () => {
      const categories = await getCategories();

      const formattedCategories = categories.map(
        category =>
          ({
            label: category.name,
            value: category.id,
          }) as SelectItem
      );

      setOptions(formattedCategories);
      dispatch(setCategories(categories));
      setIsLoading(false);
    };

    useEffect(() => {
      void getOptions();
    }, []);

    return (
      <SelectFieldAdmin
        ref={ref}
        options={options}
        disabled={isLoading}
        {...props}
      />
    );
  }
);

export default CategorySelect;
