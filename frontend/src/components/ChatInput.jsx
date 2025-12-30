import React, { useState } from 'react'
import './ChatInput.css'

function ChatInput({ onSend, disabled }) {
  const [input, setInput] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (input.trim() && !disabled) {
      onSend(input)
      setInput('')
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <form className="chat-input-form" onSubmit={handleSubmit}>
      <div className="chat-input-container">
        <input
          type="text"
          className="chat-input"
          placeholder="请输入您要查找的电路图关键词..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={disabled}
        />
        <button
          type="submit"
          className="send-button"
          disabled={disabled || !input.trim()}
        >
          发送
        </button>
      </div>
    </form>
  )
}

export default ChatInput

