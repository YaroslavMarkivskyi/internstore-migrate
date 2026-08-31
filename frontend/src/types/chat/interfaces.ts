export type ChatSenderType = 'customer' | 'admin' | 'assistant' | 'guest';

export type ChatConnectionStatus = 'connecting' | 'open' | 'closed';

export interface ChatMessage {
  id: string;
  senderType: ChatSenderType;
  senderId: string;
  content: string;
  createdAt: string;
}

/** Server -> client frame on the `/ws/room/{room_id}` socket. */
export interface ChatHistoryFrame {
  type: 'history';
  messages: Array<{
    id: string;
    sender_type: ChatSenderType;
    sender_id: string;
    content: string | null;
    attachment_url: string | null;
    created_at: string;
  }>;
}

export interface ChatMessageFrame {
  type: 'message';
  room_id: string;
  sender_type: ChatSenderType;
  sender_id: string;
  content: string | null;
  attachment_url: string | null;
  created_at: string;
}

export interface ChatTypingFrame {
  type: 'typing';
  room_id: string;
  sender_id: string;
}

export type ChatServerFrame =
  | ChatHistoryFrame
  | ChatMessageFrame
  | ChatTypingFrame;
