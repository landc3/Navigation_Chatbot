import React from 'react'
import './ChatMessage.css'

function ChatMessage({ message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`chat-message ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-content">
        <div className="message-text">
          {message.content.split('\n').map((line, index) => (
            <React.Fragment key={index}>
              {line}
              {index < message.content.split('\n').length - 1 && <br />}
            </React.Fragment>
          ))}
        </div>
        {message.results && message.results.length > 0 && (
          <div className="message-results">
            <h4>搜索结果：</h4>
            <ul>
              {message.results.map((result, index) => (
                <li key={index}>
                  <strong>[ID: {result.id}]</strong> {result.file_name}
                  <div className="result-path">{result.hierarchy_path}</div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

export default ChatMessage

