import { useCallback, useEffect, useRef, useState } from 'react';

import { auth } from '@services/firebase/client';
import { SERVER_URL } from '@services/http/api';
import { selectCurrentUser } from '@store/reducers/auth';
import { useSelector } from '@store/store';

import {
  ChatConnectionStatus,
  ChatMessage,
  ChatServerFrame,
} from '../types/chat/interfaces';

// Browsers' WebSocket API can't send an Authorization header on the
// handshake, so nginx's /ws/ location accepts a ?token= query param
// instead (see nginx/nginx.conf). We mint a fresh Firebase ID token per
// connection rather than reusing the possibly-stale one in the store.
const buildSocketUrl = (roomId: string, token: string): string => {
  const wsBase = SERVER_URL.replace(/^http/, 'ws').replace(/\/api\/?$/, '');
  return `${wsBase}/ws/room/${roomId}?token=${encodeURIComponent(token)}`;
};

interface OutgoingMessageFrame {
  type: 'message';
  content: string;
  viewing_product_id?: string;
  viewing_category_id?: string;
}

export interface ViewingContext {
  productId?: string | null;
  categoryId?: string | null;
}

const buildMessageFrame = (
  text: string,
  viewing: ViewingContext
): OutgoingMessageFrame => {
  const frame: OutgoingMessageFrame = { type: 'message', content: text };
  if (viewing.productId) {
    frame.viewing_product_id = viewing.productId;
  }
  if (viewing.categoryId) {
    frame.viewing_category_id = viewing.categoryId;
  }
  return frame;
};

const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 15000;
// The assistant runs a Gemini ReAct loop (search + cart tools), so its
// reply can legitimately take a few seconds — but don't show the "typing"
// hint forever if it never answers.
const ASSISTANT_REPLY_TIMEOUT_MS = 90000;
// nginx mints the downstream internal token once, at handshake time, with
// a 60s TTL (auth-backend's internal_token_ttl_seconds). Chat forwards
// that same token when it notifies the shopping agent, so on a socket
// that's been open longer than the TTL the notify call 401s and the
// assistant silently never replies. Cycle the socket before that window
// closes so every send rides a freshly-minted token.
const TOKEN_STALE_MS = 45000;

// "Clear conversation" (see ChatWidget) is a client-only action: server-side
// history is deliberately kept (support may pick the thread up), and a
// reconnect replays the whole `history` frame anyway, so a cleared panel
// would refill within the token-cycle window. Instead we persist a per-room
// cutoff timestamp and hide every message at or before it. The shopping
// agent still receives full server-side history for context — this only
// changes what the customer sees.
const clearedStorageKey = (roomId: string): string => `chat:cleared:${roomId}`;

const readClearedAt = (roomId: string): string | null => {
  try {
    return globalThis.localStorage?.getItem(clearedStorageKey(roomId)) ?? null;
  } catch {
    return null;
  }
};

const writeClearedAt = (roomId: string, iso: string): void => {
  try {
    globalThis.localStorage?.setItem(clearedStorageKey(roomId), iso);
  } catch {
    // Private mode / storage disabled — the clear still holds for this
    // session via in-memory state, it just won't survive a reconnect.
  }
};

interface UseChatRoomResult {
  messages: ChatMessage[];
  status: ChatConnectionStatus;
  assistantThinking: boolean;
  /** The assistant's reply so far while it streams, or null between replies. */
  streamingText: string | null;
  sendMessage: (text: string) => void;
  clearConversation: () => void;
}

export const useChatRoom = (
  enabled: boolean,
  viewing: ViewingContext = {}
): UseChatRoomResult => {
  const currentUser = useSelector(selectCurrentUser);
  const roomId = currentUser ? `room_${currentUser.user_id}` : null;

  // Kept in a ref so a route change (different product / category page)
  // doesn't churn the socket — it's only read at send time.
  const viewingRef = useRef(viewing);
  viewingRef.current = viewing;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatConnectionStatus>('closed');
  const [assistantThinking, setAssistantThinking] = useState(false);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  // The stream_id of the reply currently building in streamingText.
  const streamIdRef = useRef<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const connectedAtRef = useRef(0);
  const shouldReconnectRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const assistantTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // A message the user hit send on while the socket was stale/closed —
  // delivered by connectAndFlush()'s onopen once a fresh socket is up.
  const pendingMessageRef = useRef<string | null>(null);
  const connectRef = useRef<() => void>(() => {});
  // Messages at or before this ISO timestamp are hidden from the panel —
  // set by clearConversation, seeded from localStorage per room.
  const clearedAtRef = useRef<string | null>(null);

  useEffect(() => {
    clearedAtRef.current = roomId ? readClearedAt(roomId) : null;
  }, [roomId]);

  const isVisible = useCallback(
    (createdAt: string): boolean =>
      !clearedAtRef.current || createdAt > clearedAtRef.current,
    []
  );

  const clearAssistantTimer = useCallback(() => {
    if (assistantTimerRef.current) {
      clearTimeout(assistantTimerRef.current);
      assistantTimerRef.current = null;
    }
  }, []);

  const markAssistantThinking = useCallback(() => {
    setAssistantThinking(true);
    clearAssistantTimer();
    assistantTimerRef.current = setTimeout(
      () => setAssistantThinking(false),
      ASSISTANT_REPLY_TIMEOUT_MS
    );
  }, [clearAssistantTimer]);

  useEffect(() => {
    if (!enabled || !roomId) {
      return;
    }

    shouldReconnectRef.current = true;
    let disposed = false;

    const sendRaw = (text: string) => {
      socketRef.current?.send(
        JSON.stringify(buildMessageFrame(text, viewingRef.current))
      );
      markAssistantThinking();
    };

    const connect = async () => {
      if (disposed) {
        return;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      const token = await auth.currentUser?.getIdToken().catch(() => null);
      if (disposed || !token) {
        return;
      }

      setStatus('connecting');
      const socket = new WebSocket(buildSocketUrl(roomId, token));
      socketRef.current = socket;

      socket.onopen = () => {
        reconnectAttemptsRef.current = 0;
        connectedAtRef.current = Date.now();
        setStatus('open');
        // A stream in flight can't survive a socket swap — the history
        // frame that follows carries the persisted final message.
        streamIdRef.current = null;
        setStreamingText(null);
        if (pendingMessageRef.current) {
          const queued = pendingMessageRef.current;
          pendingMessageRef.current = null;
          sendRaw(queued);
        }
      };

      socket.onmessage = event => {
        let frame: ChatServerFrame;
        try {
          frame = JSON.parse(event.data);
        } catch {
          return;
        }

        if (frame.type === 'history') {
          streamIdRef.current = null;
          setStreamingText(null);
          setMessages(
            frame.messages
              .filter(message => message.content && isVisible(message.created_at))
              .map(message => ({
                id: message.id,
                senderType: message.sender_type,
                senderId: message.sender_id,
                content: message.content as string,
                createdAt: message.created_at,
              }))
          );
          return;
        }

        if (frame.type === 'message_delta') {
          clearAssistantTimer();
          setAssistantThinking(false);
          if (streamIdRef.current !== frame.stream_id) {
            streamIdRef.current = frame.stream_id;
            setStreamingText(frame.delta);
          } else {
            setStreamingText(prev => (prev ?? '') + frame.delta);
          }
          return;
        }

        if (frame.type === 'message_reset') {
          if (streamIdRef.current === frame.stream_id) {
            setStreamingText('');
          }
          return;
        }

        if (frame.type === 'message_done') {
          streamIdRef.current = null;
          setStreamingText(null);
          clearAssistantTimer();
          setAssistantThinking(false);
          const createdAt = frame.created_at ?? new Date().toISOString();
          if (frame.content && isVisible(createdAt)) {
            setMessages(prev => [
              ...prev,
              {
                id: frame.stream_id,
                senderType: frame.sender_type ?? 'assistant',
                senderId: frame.sender_id ?? 'ai-assistant',
                content: frame.content,
                createdAt,
              },
            ]);
          }
          return;
        }

        if (frame.type === 'message' && frame.content) {
          if (!isVisible(frame.created_at)) {
            return;
          }
          if (frame.sender_type === 'assistant') {
            clearAssistantTimer();
            setAssistantThinking(false);
          }
          setMessages(prev => [
            ...prev,
            {
              id:
                globalThis.crypto?.randomUUID?.() ??
                `${frame.created_at}-${frame.sender_id}-${prev.length}`,
              senderType: frame.sender_type,
              senderId: frame.sender_id,
              content: frame.content as string,
              createdAt: frame.created_at,
            },
          ]);
        }
      };

      socket.onclose = () => {
        if (socketRef.current === socket) {
          socketRef.current = null;
        }
        setStatus('closed');
        if (!shouldReconnectRef.current) {
          return;
        }
        const delay = Math.min(
          RECONNECT_BASE_DELAY_MS * 2 ** reconnectAttemptsRef.current,
          RECONNECT_MAX_DELAY_MS
        );
        reconnectAttemptsRef.current += 1;
        reconnectTimerRef.current = setTimeout(connect, delay);
      };

      socket.onerror = () => socket.close();
    };

    connectRef.current = () => {
      connect();
    };
    connect();

    return () => {
      disposed = true;
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      clearAssistantTimer();
      pendingMessageRef.current = null;
      socketRef.current?.close();
      socketRef.current = null;
      setStatus('closed');
      setAssistantThinking(false);
      streamIdRef.current = null;
      setStreamingText(null);
    };
  }, [enabled, roomId, clearAssistantTimer, markAssistantThinking, isVisible]);

  const clearConversation = useCallback(() => {
    setMessages(prev => {
      const cutoff =
        prev.reduce((max, message) => (message.createdAt > max ? message.createdAt : max), '') ||
        new Date().toISOString();
      clearedAtRef.current = cutoff;
      if (roomId) {
        writeClearedAt(roomId, cutoff);
      }
      return [];
    });
    setAssistantThinking(false);
    clearAssistantTimer();
    streamIdRef.current = null;
    setStreamingText(null);
  }, [roomId, clearAssistantTimer]);

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) {
        return;
      }
      const socket = socketRef.current;
      const isOpen = socket?.readyState === WebSocket.OPEN;
      const fresh =
        isOpen && Date.now() - connectedAtRef.current < TOKEN_STALE_MS;

      if (socket && fresh) {
        socket.send(
          JSON.stringify(
            buildMessageFrame(trimmed, viewingRef.current)
          )
        );
        markAssistantThinking();
        return;
      }

      // Stale or not connected — queue it and get a fresh socket (nginx
      // re-mints the 60s internal token on the new handshake). onopen
      // flushes the queue.
      pendingMessageRef.current = trimmed;
      if (socket && isOpen) {
        socket.close();
      } else if (!socket) {
        connectRef.current();
      }
    },
    [markAssistantThinking]
  );

  return {
    messages,
    status,
    assistantThinking,
    streamingText,
    sendMessage,
    clearConversation,
  };
};
