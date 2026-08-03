import { useNavigate } from 'react-router-dom';

import { Typography } from '@mui/material';

import ButtonCustomer from '@components/UI/customer/ButtonCustomer';
import colors from '@constants/colors';

import { ErrorContainer } from './styles';

const Page404 = () => {
  const navigate = useNavigate();

  return (
    <ErrorContainer>
      <Typography
        variant="h1"
        component="h1"
        sx={{ fontSize: '120px', fontWeight: 500 }}
      >
        404
      </Typography>
      <Typography variant="h4" component="h2" sx={{ mb: 2 }}>
        Page Not Found
      </Typography>
      <Typography variant="body1" color={colors.text500} sx={{ mb: 4 }}>
        The page you are looking for doesn't exist or has been moved.
      </Typography>
      <ButtonCustomer
        variant="contained"
        onClick={() => navigate('/')}
        size="large"
      >
        Back to Home
      </ButtonCustomer>
    </ErrorContainer>
  );
};

export default Page404;
