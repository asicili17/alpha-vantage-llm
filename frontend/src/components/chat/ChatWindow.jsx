/**
 * ChatWindow component - main chat container
 */

import { Box, Alert } from '@mui/material';
import MessageList from './MessageList';
import InputBar from './InputBar';

/**
 * Main chat interface container that orchestrates message display and input
 * @param {Object} props
 * @param {Array} props.messages - Array of message objects
 * @param {boolean} props.loading - Whether the assistant is responding
 * @param {string|null} props.error - Error message to display (if any)
 * @param {Function} props.onSendMessage - Callback when user sends a message
 * @param {number} props.inputKey - Key to force remount InputBar on new chat
 */
function ChatWindow({ messages, loading, error, onSendMessage, inputKey }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {error && (
        <Alert severity="error" sx={{ m: 1 }}>
          {error}
        </Alert>
      )}
      <Box sx={{ flex: 1, overflow: 'hidden' }}>
        <MessageList messages={messages} loading={loading} />
      </Box>
      <InputBar key={inputKey} onSend={onSendMessage} disabled={loading} />
    </Box>
  );
}

export default ChatWindow;
