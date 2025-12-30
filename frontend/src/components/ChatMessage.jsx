import React from 'react'
import './ChatMessage.css'

function ChatMessage({ message, onOptionClick }) {
  const isUser = message.role === 'user'

  const handleOptionClick = (option) => {
    if (onOptionClick) {
      // 发送选项标签或名称
      onOptionClick(option.label || option.name)
    }
  }

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
        {message.options && message.options.length > 0 && (
          <div className="message-options">
            <div className="options-list">
              {message.options.map((option, index) => (
                <button
                  key={index}
                  className="option-button"
                  onClick={() => handleOptionClick(option)}
                >
                  <span className="option-label">{option.label}</span>
                  <span className="option-name">{option.name}</span>
                  <span className="option-count">({option.count}个结果)</span>
                </button>
              ))}
            </div>
          </div>
        )}
        {message.results && message.results.length > 0 && (
          <div className="message-results">
            <h4>搜索结果：</h4>
            <ul>
              {message.results.map((result, index) => (
                <li key={index}>
                  <strong>[ID: {result.id}]</strong> {result.file_name}
                  <div className="result-path">{result.hierarchy_path}</div>
                  {result.brand && (
                    <div className="result-meta">
                      {result.brand && <span>品牌: {result.brand}</span>}
                      {result.model && <span>型号: {result.model}</span>}
                      {result.diagram_type && <span>类型: {result.diagram_type}</span>}
                    </div>
                  )}
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

