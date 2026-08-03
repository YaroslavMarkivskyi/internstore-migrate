import { forwardRef } from 'react';

import { InputFieldProps } from '../../admin/InputFieldAdmin';

import { InputFieldBase } from './styles';

/** Basic Input Field for Customer Pages */
const InputFieldCustomer = forwardRef<HTMLInputElement, InputFieldProps>(
  (props, ref) => {
    return <InputFieldBase ref={ref} {...props} />;
  }
);

export default InputFieldCustomer;
