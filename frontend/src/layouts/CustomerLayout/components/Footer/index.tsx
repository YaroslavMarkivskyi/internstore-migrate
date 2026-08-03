import { useRef } from 'react';

import { useNavigate } from 'react-router';

import Logo from '@components/UI/common/Logo';
import {
  ConnectWithUsContainer,
  ConnectWithUsIcon,
  FooterContainer,
  FooterTypography,
  FooterWrapper,
} from '@layouts/CustomerLayout/components/Footer/styles';

const Footer = () => {
  const currentDate = useRef(new Date());
  const formattedDate = currentDate.current.toLocaleDateString('en-GB');

  const navigate = useNavigate();

  return (
    <FooterContainer>
      <FooterWrapper
        sx={{
          px: { xs: 2, md: '80px' },
        }}
      >
        <Logo onClick={() => navigate('/')} />
        <FooterTypography>{formattedDate}</FooterTypography>
        <ConnectWithUsContainer href="mailto:hello@chisw.com">
          <ConnectWithUsIcon fontSize="large" />
          <FooterTypography>Connect With Us</FooterTypography>
        </ConnectWithUsContainer>
      </FooterWrapper>
    </FooterContainer>
  );
};

export default Footer;
