import { useNavigate } from 'react-router-dom';

import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { Typography } from '@mui/material';

import ButtonCustomer from '@components/UI/customer/ButtonCustomer';
import colors from '@constants/colors';

import { ErrorContainer } from './styles';

const Page403 = () => {
  const navigate = useNavigate();

  return (
    <ErrorContainer>
      <LockOutlinedIcon
        sx={{ fontSize: 120, color: colors.secondary.accent100 }}
      />
      <Typography
        variant="h1"
        component="h1"
        sx={{ fontSize: '120px', fontWeight: 500 }}
      >
        403
      </Typography>
      <Typography variant="h4" component="h2" sx={{ mb: 2 }}>
        Access Forbidden
      </Typography>
      <Typography variant="body1" color={colors.text500} sx={{ mb: 4 }}>
        You don't have permission to access this page.
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

export default Page403;
