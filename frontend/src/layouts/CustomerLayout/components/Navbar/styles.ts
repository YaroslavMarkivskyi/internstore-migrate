import PersonOutlinedIcon from '@mui/icons-material/PersonOutlined';
import { IconButton, styled } from '@mui/material';

export const StyledIconButton = styled(IconButton)({
  boxShadow: '0px 4px 15px #E0E0E0',
});

export const ProfileIcon = styled(PersonOutlinedIcon)(({ theme }) => ({
  margin: theme.spacing(0.5),
}));
