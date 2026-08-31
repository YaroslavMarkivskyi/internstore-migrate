import { FC, useLayoutEffect, useMemo, useRef, useState } from 'react';

import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import CloseIcon from '@mui/icons-material/Close';
import DeleteSweepOutlinedIcon from '@mui/icons-material/DeleteSweepOutlined';
import SendIcon from '@mui/icons-material/Send';
import { IconButton, InputBase } from '@mui/material';

import { selectCurrentUser } from '@store/reducers/auth';
import { useSelector } from '@store/store';

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
} from '../ChatWidget/styles';

import { useChatRoom } from '../../hooks/useChatRoom';

const STATUS_LABEL = {
  connecting: 'Connecting…',
  open: 'Online',
  closed: 'Reconnecting…',
} as const;

/**
 * Floating read-only ops assistant for staff — mounted in AdminLayout.
 * Talks to the admin's own `room_ops_<sub>` room; Chat routes messages
 * there to ai-assistant's POST /agent/admin (see ws/room.py).
 */
const OpsAssistant: FC = () => {
  const currentUser = useSelector(selectCurrentUser);
  const isAdmin = Boolean(currentUser?.is_admin);

  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');

  const opsRoomId = currentUser ? `room_ops_${currentUser.user_id}` : null;
  const {
    messages,
    status,
    assistantThinking,
    streamingText,
    sendMessage,
    clearConversation,
  } = useChatRoom(isAdmin && open, {}, opsRoomId);

  const bodyRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const node = bodyRef.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [messages, assistantThinking, streamingText, open]);

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
        const mine = message.senderType === 'admin';
        return (
          <Bubble key={message.id} mine={mine}>
            {!mine && <SenderTag>Ops assistant</SenderTag>}
            {message.content}
          </Bubble>
        );
      }),
    [messages]
  );

  if (!isAdmin) {
    return null;
  }

  if (!open) {
    return (
      <LauncherButton
        aria-label="Open ops assistant"
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
          <HeaderTitle>Ops Assistant</HeaderTitle>
          <StatusLine>{STATUS_LABEL[status]}</StatusLine>
        </div>
        <div>
          <IconButton
            size="small"
            aria-label="Clear conversation"
            title="Clear conversation"
            disabled={messages.length === 0}
            onClick={clearConversation}
            sx={{
              color: '#FFFFFF',
              '&.Mui-disabled': { color: 'rgba(255,255,255,0.35)' },
            }}
          >
            <DeleteSweepOutlinedIcon fontSize="small" />
          </IconButton>
          <IconButton
            size="small"
            aria-label="Close ops assistant"
            onClick={() => setOpen(false)}
            sx={{ color: '#FFFFFF' }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </div>
      </Header>

      <Body ref={bodyRef}>
        {messages.length === 0 &&
          !assistantThinking &&
          streamingText === null && (
            <EmptyState>
              Ask about platform state — e.g. “any orders stuck in pending?”,
              “cold-chain incidents today?”, “what’s low on stock?”.
            </EmptyState>
          )}
        {rendered}
        {streamingText !== null ? (
          <Bubble mine={false}>
            <SenderTag>Ops assistant</SenderTag>
            {streamingText || 'typing…'}
          </Bubble>
        ) : (
          assistantThinking && (
            <Bubble mine={false}>
              <SenderTag>Ops assistant</SenderTag>
              typing…
            </Bubble>
          )
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

export default OpsAssistant;
