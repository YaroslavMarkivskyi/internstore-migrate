import { useNavigate } from 'react-router';

import { zodResolver } from '@hookform/resolvers/zod';
import CloseIcon from '@mui/icons-material/Close';
import { Controller, SubmitHandler, useForm } from 'react-hook-form';

import PasswordField from '@components/UI/common/PasswordField';
import ButtonCustomer from '@components/UI/customer/ButtonCustomer';
import InputFieldCustomer from '@components/UI/customer/InputFieldCustomer';
import { login } from '@services/http/public/auth';
import { mergeCart } from '@services/http/public/cart';
import { setCredentials } from '@store/reducers/auth';
import { useDispatch } from '@store/store';
import { handleFormErrors } from '@utils/handleFormErrors';

import { ErrorText, StyledIconButton } from '../styles';

import { LoginCredentials } from '../../../types/auth/interfaces';
import { LoginFormData } from '../../../types/auth/types';

import {
  ButtonsContainer,
  InputsContainer,
  LoginContainer,
  LoginTitle,
} from './styles';
import { loginSchema } from './validation';

interface CustomerLoginComponentProps {
  switchToSignUp: () => void;
  onClose: () => void;
}

const CustomerLoginComponent: React.FC<CustomerLoginComponentProps> = ({
  switchToSignUp,
  onClose,
}) => {
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const {
    control,
    handleSubmit,
    setError,
    formState: {
      errors,
      isDirty,
      isValid,
      isSubmitted,
      isSubmitting,
      isLoading,
    },
  } = useForm({
    resolver: zodResolver(loginSchema),
    mode: 'onSubmit',
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit: SubmitHandler<LoginFormData> = async data => {
    try {
      const credentials: LoginCredentials = {
        email: data.email,
        password: data.password,
      };

      const response = await login(credentials);
      await mergeCart(response.access);

      dispatch(setCredentials(response));

      onClose();
      navigate('/');
    } catch (error: unknown) {
      handleFormErrors<LoginFormData>(error, setError);
    }
  };

  const shouldDisableButton =
    !isDirty || (isSubmitted && !isValid) || isLoading;
  const buttonVariant = isDirty ? 'contained' : 'contained';

  return (
    <LoginContainer onSubmit={handleSubmit(onSubmit)}>
      <StyledIconButton onClick={onClose} aria-label="close">
        <CloseIcon />
      </StyledIconButton>

      <LoginTitle data-testid="login-title">Log in</LoginTitle>

      <InputsContainer spacing={3}>
        <div>
          <Controller
            name="email"
            control={control}
            render={({ field }) => (
              <InputFieldCustomer
                {...field}
                placeholder="Email"
                error={errors.email?.message}
              />
            )}
          />
        </div>
        <div>
          <Controller
            name="password"
            control={control}
            render={({ field }) => (
              <PasswordField
                {...field}
                placeholder="Password"
                error={errors.password?.message}
              />
            )}
          />
        </div>
      </InputsContainer>

      <ButtonsContainer spacing={2}>
        <ButtonCustomer
          type="submit"
          loading={isSubmitting}
          variant={buttonVariant}
          disabled={shouldDisableButton}
        >
          Log in
        </ButtonCustomer>
        <ButtonCustomer variant="outlined" onClick={switchToSignUp}>
          Sign up
        </ButtonCustomer>
      </ButtonsContainer>

      {errors.root && (
        <ErrorText sx={{ mt: 1 }}>{errors.root.message}</ErrorText>
      )}
    </LoginContainer>
  );
};

export default CustomerLoginComponent;
