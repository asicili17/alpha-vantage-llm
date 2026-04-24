/**
 * API client for chat interactions
 */

/**
 * Send a chat message to the backend
 * @param {string|null} conversationId - Current conversation ID (null for new conversation)
 * @param {string} message - User message text
 * @returns {Promise<Object>} Response with conversation_id, assistant_message, citations, intent, needs_clarification
 * @throws {Error} If the request fails
 */
export async function sendChatMessage(conversationId, message) {
  const response = await fetch('/api/chat/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversation_id: conversationId,
      message: message
    })
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || `HTTP ${response.status}`);
  }
  
  return response.json();
}
