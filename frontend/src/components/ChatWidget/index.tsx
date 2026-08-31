import {
  FC,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { useMatch } from 'react-router-dom';

import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import CloseIcon from '@mui/icons-material/Close';
import DeleteSweepOutlinedIcon from '@mui/icons-material/DeleteSweepOutlined';
import SendIcon from '@mui/icons-material/Send';
import { IconButton, InputBase } from '@mui/material';

import { selectCurrentUser } from '@store/reducers/auth';
import { useSelector } from '@store/store';

import { useCart } from '../../hooks/useCart';
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

  // The customer-facing product route (not /admin/products/preview/:id) —
  // gives the agent an antecedent for "this product" / "it".
  const productMatch = useMatch('/products/:id');
  const viewingProductId = productMatch?.params.id ?? null;

  const {
    messages,
    status,
    assistantThinking,
    streamingText,
    sendMessage,
    clearConversation,
  } = useChatRoom(isCustomer && open, viewingProductId);

  // The agent can mutate the cart server-side (add_to_cart / remove_from_cart)
  // — pull a fresh cart whenever it finishes a reply so the header badge and
  // the Cart modal reflect it without a page reload. fetchCart/fetchCartItems
  // aren't memoised in useCart, so key the effect off the reply count only.
  const cart = useCart();
  const cartRef = useRef(cart);
  cartRef.current = cart;
  const assistantReplyCount = useMemo(
    () => messages.filter(m => m.senderType === 'assistant').length,
    [messages]
  );
  useEffect(() => {
    if (assistantReplyCount === 0) {
      return;
    }
    void cartRef.current.fetchCart();
    void cartRef.current.fetchCartItems({ offset: 0 }, true);
  }, [assistantReplyCount]);

  const bodyRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const node = bodyRef.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [messages, assistantThinking, streamingText, open]);

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
        <div>
          <IconButton
            size="small"
            aria-label="Clear conversation"
            title="Clear conversation"
            disabled={messages.length === 0}
            onClick={clearConversation}
            sx={{ color: '#FFFFFF', '&.Mui-disabled': { color: 'rgba(255,255,255,0.35)' } }}
          >
            <DeleteSweepOutlinedIcon fontSize="small" />
          </IconButton>
          <IconButton
            size="small"
            aria-label="Close chat"
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
              Ask about products, prices or your cart — e.g. “find me a Gouda
              under $20”.
            </EmptyState>
          )}
        {rendered}
        {streamingText !== null ? (
          <Bubble mine={false}>
            <SenderTag>Assistant</SenderTag>
            {streamingText
              ? renderMessageContent(streamingText)
              : 'typing…'}
          </Bubble>
        ) : (
          assistantThinking && (
            <Bubble mine={false}>
              <SenderTag>Assistant</SenderTag>
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

export default ChatWidget;
