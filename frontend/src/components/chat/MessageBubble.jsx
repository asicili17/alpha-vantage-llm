/**
 * MessageBubble component - displays a single chat message
 */

import { Box, Paper, Typography } from '@mui/material';
import Citations from '../common/Citations';
import TypewriterText from './TypewriterText';

/**
 * Renders a single message bubble with optional citations
 * @param {Object} props
 * @param {string} props.role - 'user' or 'assistant'
 * @param {string} props.content - Message text content
 * @param {Array} props.citations - Optional array of citations (for assistant messages)
 */
function MessageBubble({ role, content, citations }) {
  const isUser = role === 'user';
  
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        mb: 1,
      }}
    >
      <Paper
        elevation={1}
        sx={{
          maxWidth: '70%',
          p: 2,
          bgcolor: isUser ? '#001a00' : '#0a0a0a',
          color: isUser ? '#00ff00' : '#00cc00',
          border: '1px solid',
          borderColor: isUser ? '#00ff00' : '#003300',
        }}
      >
        {isUser ? (
          <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {content}
          </Typography>
        ) : (
          <TypewriterText content={content} speed={7} />
        )}
        {citations && citations.length > 0 && <Citations citations={citations} />}
      </Paper>
    </Box>
  );
}

export default MessageBubble;
