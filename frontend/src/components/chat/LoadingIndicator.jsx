import { Box } from '@mui/material';
import './LoadingIndicator.css';

/**
 * Renders an animated honeycomb loading indicator as an assistant message
 */
function LoadingIndicator() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 1 }}>
      <Box
        sx={{
          p: 2,
          bgcolor: '#0a0a0a',
          border: '1px solid #003300',
          borderRadius: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <div className="honeycomb">
          <div></div>
          <div></div>
          <div></div>
          <div></div>
          <div></div>
          <div></div>
          <div></div>
        </div>
      </Box>
    </Box>
  );
}

export default LoadingIndicator;
