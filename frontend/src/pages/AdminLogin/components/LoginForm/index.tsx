import { zodResolver } from '@hookform/resolvers/zod';
import { Typography } from '@mui/material';
import { useForm, UseFormSetError } from 'react-hook-form';

import { ErrorText } from '../../../../components/auth/styles';
import PasswordField from '../../../../components/UI/common/PasswordField';
import ButtonCustomer from '../../../../components/UI/customer/ButtonCustomer';
import InputFieldCustomer from '../../../../components/UI/customer/InputFieldCustomer';
import { loginSchema } from '../../../../schemas/login';
import { LoginDataType } from '../../../../types/schemaTypes';

import { FormControlStyled, FormWrapper } from './styles';

export default function LoginForm(
  {
    onSubmit,
  }: {
    onSubmit: (
      data: LoginDataType,
      setError: UseFormSetError<LoginDataType>
    ) => void;
  } = { onSubmit: () => {} }
) {
  const {
    register,
    handleSubmit,
    formState: { errors, isValid, isDirty, isSubmitted, isLoading },
    setError,
    clearErrors,
    getFieldState,
  } = useForm<LoginDataType>({
    resolver: zodResolver(loginSchema),
    mode: 'onSubmit',
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const handleFormSubmit = (data: LoginDataType) => {
    onSubmit(data, setError);
  };

  const handleManualErrorCleanup = (field: keyof LoginDataType) => {
    const otherField: keyof LoginDataType =
      field === 'email' ? 'password' : 'email';
    const otherFieldState = getFieldState(otherField);

    if (otherFieldState.error?.type === 'manual') {
      clearErrors(otherField);
    }
  };
  const shouldDisableButton =
    !isDirty || (isSubmitted && !isValid && !errors.root) || isLoading;
  return (
    <FormWrapper>
      <Typography>Log In</Typography>
      <FormControlStyled onSubmit={handleSubmit(handleFormSubmit)}>
        <InputFieldCustomer
          placeholder="Email"
          {...register('email', {
            onChange: () => handleManualErrorCleanup('email'),
          })}
          error={errors.email?.message}
        />
        <PasswordField
          placeholder="Password"
          {...register('password', {
            onChange: () => handleManualErrorCleanup('password'),
          })}
          error={errors.password?.message}
        />
        {errors.root && (
          <ErrorText sx={{ mt: 1 }}>{errors.root.message}</ErrorText>
        )}
        <ButtonCustomer
          type="submit"
          disabled={shouldDisableButton}
          variant="contained"
          fullWidth
        >
          Log in
        </ButtonCustomer>
      </FormControlStyled>
    </FormWrapper>
  );
}
