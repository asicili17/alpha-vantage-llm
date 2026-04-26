import { useState } from 'react';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Tooltip
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ChatWindow from './components/chat/ChatWindow';
import { sendChatMessage } from './api/chat';

function App() {
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [chatResetCounter, setChatResetCounter] = useState(0);

  const handleNewChat = () => {
    setConversationId(null);
    setMessages([]);
    setError(null);
    setChatResetCounter(prev => prev + 1);
  };

  const handleSendMessage = async (userMessage) => {
    // Clear any previous errors
    setError(null);
    
    // Add user message to chat immediately
    const userMessageObj = {
      role: 'user',
      content: userMessage
    };
    setMessages(prev => [...prev, userMessageObj]);
    
    // Set loading state
    setLoading(true);
    
    try {
      // Call backend API
      const response = await sendChatMessage(conversationId, userMessage);
      
      // Update conversation ID if this is first message
      if (!conversationId && response.conversation_id) {
        setConversationId(response.conversation_id);
      }
      
      // Add assistant response to chat
      const assistantMessageObj = {
        role: 'assistant',
        content: response.assistant_message,
        citations: response.citations || []
      };
      setMessages(prev => [...prev, assistantMessageObj]);
      
    } catch (err) {
      console.error('Error sending message:', err);
      setError(err.message || 'Failed to send message. Please try again.');
      
      // Add error message to chat
      const errorMessageObj = {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${err.message || 'Unknown error'}. Please try again.`
      };
      setMessages(prev => [...prev, errorMessageObj]);
      
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <AppBar position="static" elevation={1}>
        <Toolbar>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6" component="h1">
              Earnings Call Analysis Agent
            </Typography>
            <Typography variant="caption" sx={{ opacity: 0.9 }}>
              Ask questions about company earnings calls
            </Typography>
          </Box>
          <Tooltip title="New chat">
            <IconButton
              color="inherit"
              onClick={handleNewChat}
              disabled={loading}
            >
              <AddIcon />
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>
      <Box sx={{ flex: 1, overflow: 'hidden' }}>
        <ChatWindow
          messages={messages}
          loading={loading}
          error={error}
          onSendMessage={handleSendMessage}
          inputKey={chatResetCounter}
        />
      </Box>
    </Box>
  );
}

export default App;
