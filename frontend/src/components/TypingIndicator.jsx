import React from 'react'
import './TypingIndicator.css'

function TypingIndicator() {
  return (
    <div className="typing-row" aria-label="assistant typing">
      <div className="typing-bubble">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  )
}

export default TypingIndicator




