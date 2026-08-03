import React from 'react';

import { useNavigate } from 'react-router';

import { zodResolver } from '@hookform/resolvers/zod';
import CloseIcon from '@mui/icons-material/Close';
import DoneIcon from '@mui/icons-material/Done';
import { Box, Stack, Typography } from '@mui/material';
import { Controller, SubmitHandler, useForm } from 'react-hook-form';

import { signUp } from '@services/http/public/auth';

import { ErrorText, StyledIconButton } from '../styles';

import { setCredentials } from '../../../store/reducers/auth';
import { useDispatch } from '../../../store/store';
import { handleFormErrors } from '../../../utils/handleFormErrors';
import PasswordField from '../../UI/common/PasswordField';
import ButtonCustomer from '../../UI/customer/ButtonCustomer';
import InputFieldCustomer from '../../UI/customer/InputFieldCustomer';

import { RuleTag, RuleText, SignUpContainer, SignUpTitle } from './styles';
import { passwordRules, SignUpFormData, signUpSchema } from './validation';

interface CustomerSignUpComponentProps {
  onClose: () => void;
}

const CustomerSignUpComponent: React.FC<CustomerSignUpComponentProps> = ({
  onClose,
}) => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const {
    control,
    handleSubmit,
    setError,
    watch,
    formState: { errors, isValid, isSubmitting },
  } = useForm<SignUpFormData>({
    resolver: zodResolver(signUpSchema),
    mode: 'onSubmit',
    defaultValues: {
      firstName: '',
      lastName: '',
      email: '',
      password: '',
    },
  });

  const password = watch('password');

  const onSubmit: SubmitHandler<SignUpFormData> = async data => {
    try {
      const credentials = {
        first_name: data.firstName,
        last_name: data.lastName,
        email: data.email,
        password: data.password,
      };

      const response = await signUp(credentials);

      dispatch(setCredentials(response));
      onClose();
      navigate('/');
    } catch (error: unknown) {
      handleFormErrors<SignUpFormData>(error, setError);
    }
  };

  return (
    <SignUpContainer onSubmit={handleSubmit(onSubmit)}>
      <StyledIconButton onClick={onClose} aria-label="close">
        <CloseIcon />
      </StyledIconButton>

      <SignUpTitle>Sign up</SignUpTitle>

      <Stack spacing={3}>
        <Controller
          name="firstName"
          control={control}
          render={({ field }) => (
            <InputFieldCustomer
              placeholder="First Name"
              error={errors.firstName?.message}
              {...field}
            />
          )}
        />

        <Controller
          name="lastName"
          control={control}
          render={({ field }) => (
            <InputFieldCustomer
              placeholder="Last Name"
              error={errors.lastName?.message}
              {...field}
            />
          )}
        />

        <Controller
          name="email"
          control={control}
          render={({ field }) => (
            <InputFieldCustomer
              placeholder="Email"
              error={errors.email?.message}
              {...field}
            />
          )}
        />

        <Controller
          name="password"
          control={control}
          render={({ field }) => (
            <PasswordField
              placeholder="Password"
              error={errors.password?.message}
              {...field}
            />
          )}
        />

        <Box>
          <Typography variant="caption" color="text.secondary">
            Please create a secure password including the criteria below
          </Typography>
          <Stack direction="row" gap={1} flexWrap="wrap" mt={1}>
            {passwordRules.map(({ label, test }) => {
              const valid = test(password || '');
              return (
                <RuleTag key={label} valid={valid} data-testid="password-rule">
                  <Stack direction="row" alignItems="center">
                    {valid && (
                      <DoneIcon
                        fontSize="small"
                        sx={{ pl: 0.5 }}
                        data-testid="password-rule-check"
                      />
                    )}
                    <RuleText>{label}</RuleText>
                  </Stack>
                </RuleTag>
              );
            })}
          </Stack>
        </Box>

        <ButtonCustomer
          fullWidth
          variant="contained"
          disabled={!isValid}
          loading={isSubmitting}
          type="submit"
          loadingPosition="center"
        >
          {isSubmitting ? <>&nbsp;</> : 'Sign Up'}
        </ButtonCustomer>
      </Stack>

      {errors.root && (
        <ErrorText sx={{ mt: 1 }}>{errors.root.message}</ErrorText>
      )}
    </SignUpContainer>
  );
};

export default CustomerSignUpComponent;
