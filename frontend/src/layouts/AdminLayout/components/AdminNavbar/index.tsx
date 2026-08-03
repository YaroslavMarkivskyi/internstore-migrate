import { useSelector } from 'react-redux';

import { ChatBubbleOutline, NotificationsNone } from '@mui/icons-material';
import { Badge } from '@mui/material';

import { NotificationsPopup } from '@components/Notifications';
import { SearchBar } from '@components/SearchBar';
import SimplePopover from '@components/UI/common/SimplePopover';
import UserModal from '@components/UserModal';
import { selectUnreadCount } from '@store/reducers/notifications';

import {
  ActionIconButton,
  ActionsContainer,
  HeaderContainer,
  ICON_COLOR,
  SearchContainer,
  UserAvatar,
} from './styles';

const AdminNavbar = () => {
  const unreadCount = useSelector(selectUnreadCount);

  return (
    <HeaderContainer>
      <SearchContainer>
        <SearchBar area="admin" />
      </SearchContainer>
      <ActionsContainer>
        <ActionIconButton>
          <Badge badgeContent={0} color="error">
            <ChatBubbleOutline fontSize="small" sx={{ color: ICON_COLOR }} />
          </Badge>
        </ActionIconButton>

        <SimplePopover
          trigger={
            <ActionIconButton>
              <Badge badgeContent={unreadCount} color="error">
                <NotificationsNone
                  fontSize="small"
                  sx={{ color: ICON_COLOR }}
                />
              </Badge>
            </ActionIconButton>
          }
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'right',
          }}
          transformOrigin={{
            vertical: -20,
            horizontal: 'right',
          }}
          slotProps={{
            paper: { sx: { borderRadius: '10px', minWidth: '250px' } },
          }}
        >
          <NotificationsPopup />
        </SimplePopover>

        <SimplePopover
          trigger={
            <UserAvatar
              src="https://randomuser.me/api/portraits/women/79.jpg"
              alt="User"
            />
          }
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'right',
          }}
          transformOrigin={{
            vertical: -20,
            horizontal: 'right',
          }}
          slotProps={{
            paper: { sx: { borderRadius: '10px', minWidth: '250px' } },
          }}
        >
          <UserModal />
        </SimplePopover>
      </ActionsContainer>
    </HeaderContainer>
  );
};

export default AdminNavbar;
