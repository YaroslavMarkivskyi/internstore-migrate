import {
  FC,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import CloseIcon from '@mui/icons-material/Close';
import SendIcon from '@mui/icons-material/Send';
import { IconButton, InputBase } from '@mui/material';

import { selectCurrentUser } from '@store/reducers/auth';
import { useSelector } from '@store/store';

import { useChatRoom } from '../../hooks/useChatRoom';
import { ChatSenderType } from '../../types/chat/interfaces';

import { renderMessageContent } from './messageContent';
import {
  Body,
  Bubble,
  EmptyState,
  Footer,
  Header,
  HeaderTitle,
  LauncherButton,
  Panel,
  SenderTag,
  StatusLine,
} from './styles';

const SENDER_LABEL: Record<ChatSenderType, string> = {
  customer: 'You',
  guest: 'You',
  admin: 'Support',
  assistant: 'Assistant',
};

const STATUS_LABEL = {
  connecting: 'Connecting…',
  open: 'Online',
  closed: 'Reconnecting…',
} as const;

const ChatWidget: FC = () => {
  const currentUser = useSelector(selectCurrentUser);
  const isCustomer = Boolean(currentUser) && !currentUser?.is_admin;

  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');

  const { messages, status, assistantThinking, sendMessage } = useChatRoom(
    isCustomer && open
  );

  const bodyRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const node = bodyRef.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [messages, assistantThinking, open]);

  useEffect(() => {
    if (!isCustomer) {
      setOpen(false);
    }
  }, [isCustomer]);

  const handleSend = () => {
    if (!draft.trim()) {
      return;
    }
    sendMessage(draft);
    setDraft('');
  };

  const rendered = useMemo(
    () =>
      messages.map(message => {
        const mine =
          message.senderType === 'customer' || message.senderType === 'guest';
        return (
          <Bubble key={message.id} mine={mine}>
            {!mine && <SenderTag>{SENDER_LABEL[message.senderType]}</SenderTag>}
            {renderMessageContent(message.content)}
          </Bubble>
        );
      }),
    [messages]
  );

  if (!isCustomer) {
    return null;
  }

  if (!open) {
    return (
      <LauncherButton
        aria-label="Open shopping assistant"
        onClick={() => setOpen(true)}
      >
        <ChatBubbleOutlineIcon />
      </LauncherButton>
    );
  }

  return (
    <Panel>
      <Header>
        <div>
          <HeaderTitle>Shopping Assistant</HeaderTitle>
          <StatusLine>{STATUS_LABEL[status]}</StatusLine>
        </div>
        <IconButton
          size="small"
          aria-label="Close chat"
          onClick={() => setOpen(false)}
          sx={{ color: '#FFFFFF' }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Header>

      <Body ref={bodyRef}>
        {messages.length === 0 && !assistantThinking && (
          <EmptyState>
            Ask about products, prices or your cart — e.g. “find me a Gouda
            under $20”.
          </EmptyState>
        )}
        {rendered}
        {assistantThinking && (
          <Bubble mine={false}>
            <SenderTag>Assistant</SenderTag>
            typing…
          </Bubble>
        )}
      </Body>

      <Footer>
        <InputBase
          fullWidth
          multiline
          maxRows={4}
          placeholder="Type a message"
          value={draft}
          onChange={event => setDraft(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              handleSend();
            }
          }}
          sx={{ fontSize: 14 }}
        />
        <IconButton
          color="primary"
          aria-label="Send message"
          disabled={!draft.trim() || status !== 'open'}
          onClick={handleSend}
        >
          <SendIcon />
        </IconButton>
      </Footer>
    </Panel>
  );
};

export default ChatWidget;
