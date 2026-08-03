import React from 'react';

import { SelectItem } from '@components/UI/admin/SelectFieldAdmin';
import MockSelectFieldAdmin from '@components/UI/admin/SelectFieldAdmin/__mocks__/SelectFieldAdmin.mock';

type Props = {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  label: string;
  error?: string;
  multiple: boolean;
  name: string;
};

const categories: SelectItem[] = [
  { label: 'Label 1', value: 1 },
  { label: 'Label 2', value: 2 },
  { label: 'Label 3', value: 3 },
  { label: 'Label 4', value: 4 },
  { label: 'Label 5', value: 5 },
  { label: 'Label 6', value: 6 },
  { label: 'Label 7', value: 7 },
  { label: 'Label 8', value: 8 },
  { label: 'Label 9', value: 9 },
];

export default function MockCategorySelect({
  value,
  onChange,
  label,
  error,
  multiple,
  name,
}: Props) {
  return (
    <MockSelectFieldAdmin
      multiple={multiple}
      value={value}
      onChange={onChange}
      label={label}
      name={name}
      options={categories}
      error={error}
    />
  );
}
