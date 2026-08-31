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

interface UseChatRoomResult {
  messages: ChatMessage[];
  status: ChatConnectionStatus;
  assistantThinking: boolean;
  sendMessage: (text: string) => void;
}

export const useChatRoom = (enabled: boolean): UseChatRoomResult => {
  const currentUser = useSelector(selectCurrentUser);
  const roomId = currentUser ? `room_${currentUser.user_id}` : null;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatConnectionStatus>('closed');
  const [assistantThinking, setAssistantThinking] = useState(false);

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
        JSON.stringify({ type: 'message', content: text })
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
          setMessages(
            frame.messages
              .filter(message => message.content)
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

        if (frame.type === 'message' && frame.content) {
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
    };
  }, [enabled, roomId, clearAssistantTimer, markAssistantThinking]);

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
        socket.send(JSON.stringify({ type: 'message', content: trimmed }));
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

  return { messages, status, assistantThinking, sendMessage };
};
