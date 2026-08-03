import { Box, FormControlLabel, RadioGroup, Typography } from '@mui/material';
import { FormState, UseFormRegister } from 'react-hook-form';

import InputFieldCustomer from '@components/UI/customer/InputFieldCustomer';

import { CheckoutFormData } from '../../validation';

import { CustomRadio, FormHeader } from './styles';

// Free-text on the backend (orders.CheckoutRequest.payment_method is just a
// str) -- these are the only two the UI offers, not an exhaustive backend
// enum.
export const PAYMENT_METHODS = [
  { value: 'card', label: 'Card' },
  { value: 'cash_on_delivery', label: 'Cash on delivery' },
];

interface ContactInfoProps {
  register: UseFormRegister<CheckoutFormData>;
  formState: FormState<CheckoutFormData>;
  paymentMethod: string;
  onPaymentMethodChange: (value: string) => void;
}

const ContactInfo = ({
  register,
  formState,
  paymentMethod,
  onPaymentMethodChange,
}: ContactInfoProps) => {
  return (
    <>
      <FormHeader>
        <Typography mb={2}>Contact details</Typography>
      </FormHeader>

      <Box display="flex" flexDirection="row" gap={2} mb={3}>
        <InputFieldCustomer
          label="Name"
          placeholder="Full name"
          {...register('contactName')}
          error={formState.errors.contactName?.message}
          fullWidth
          errorPosition={'absolute'}
        />
        <InputFieldCustomer
          label="Email"
          placeholder="Email"
          {...register('contactEmail')}
          error={formState.errors.contactEmail?.message}
          fullWidth
          errorPosition={'absolute'}
        />
      </Box>

      <Box display="flex" flexDirection="row" gap={2} mb={3}>
        <InputFieldCustomer
          label="Phone number (optional)"
          placeholder="+380"
          {...register('contactPhone')}
          error={formState.errors.contactPhone?.message}
          fullWidth
          errorPosition={'absolute'}
        />
      </Box>

      <Typography mb={1} mt={2}>
        Payment Method
      </Typography>
      <RadioGroup
        value={paymentMethod}
        onChange={e => onPaymentMethodChange(e.target.value)}
      >
        {PAYMENT_METHODS.map(method => (
          <FormControlLabel
            key={method.value}
            value={method.value}
            control={<CustomRadio />}
            label={method.label}
          />
        ))}
      </RadioGroup>
      {formState.errors.paymentMethod && (
        <Typography color="error" fontSize={12}>
          {formState.errors.paymentMethod.message}
        </Typography>
      )}
    </>
  );
};

export default ContactInfo;
