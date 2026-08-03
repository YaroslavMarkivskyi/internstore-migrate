import { useNavigate } from 'react-router';

import axios from 'axios';

import { UseFormSetError } from 'react-hook-form';

import { adminLogin } from '@services/http/admin/auth';
import { mergeCart } from '@services/http/public/cart';
import { handleFormErrors } from '@utils/handleFormErrors';

import Logo from '../../components/UI/common/Logo';
import { setCredentials } from '../../store/reducers/auth';
import { useDispatch } from '../../store/store';
import { LoginDataType } from '../../types/schemaTypes';

import LoginForm from './components/LoginForm';
import { Container, LogoStatic } from './styles';

import { LoginFormData } from 'src/types/auth/types';

function AdminLogin() {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const onSubmit = async (
    loginData: LoginDataType,
    setError: UseFormSetError<LoginDataType>
  ) => {
    try {
      const response = await adminLogin(loginData);
      await mergeCart(response.access);
      dispatch(setCredentials(response));
      navigate('/admin/dashboard');
    } catch (error: unknown) {
      if (axios.isAxiosError(error) && error.response) {
        const { status } = error.response;
        if (status >= 400 && status < 500) {
          setError('email', {
            type: 'manual',
            message: 'Please enter a valid email',
          });
          setError('password', {
            type: 'manual',
            message: 'Please enter a valid password',
          });
        } else {
          handleFormErrors<LoginFormData>(error, setError);
        }
      } else {
        handleFormErrors<LoginFormData>(error, setError);
      }
    }
  };

  return (
    <Container>
      <LogoStatic>
        <Logo isAdmin />
      </LogoStatic>
      <LoginForm onSubmit={onSubmit} />
    </Container>
  );
}

export default AdminLogin;
