/**
 * TypewriterText component - Animates text character by character
 */

import { useState, useEffect } from 'react';
import { Typography } from '@mui/material';

/**
 * Renders text with a typewriter animation effect
 * @param {Object} props
 * @param {string} props.content - Text content to animate
 * @param {number} props.speed - Milliseconds between each character (default: 15)
 */
function TypewriterText({ content, speed = 5 }) {
  const [displayedContent, setDisplayedContent] = useState('');
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    setDisplayedContent('');
    setIsComplete(false);
    let index = 0;
    
    const interval = setInterval(() => {
      if (index < content.length) {
        setDisplayedContent(content.slice(0, index + 1));
        index++;
      } else {
        setIsComplete(true);
        clearInterval(interval);
      }
    }, speed);

    return () => clearInterval(interval);
  }, [content, speed]);

  return (
    <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {displayedContent}
      {!isComplete && <span style={{ opacity: 0.5 }}>▋</span>}
    </Typography>
  );
}

export default TypewriterText;
