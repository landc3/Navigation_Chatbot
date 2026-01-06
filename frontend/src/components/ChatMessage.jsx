import React, { useState } from 'react'
import './ChatMessage.css'

function ChatMessage({ message, onOptionClick, onQuickAction, onQuickReply, optionsDisabled = false }) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)

  const handleOptionClick = (option) => {
    if (onOptionClick) {
      // 发送选项标签或名称
      onOptionClick(option.label || option.name)
    }
  }

  const copyToClipboard = async () => {
    if (!message?.content) return
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(message.content)
      } else {
        // 兼容性兜底
        const textarea = document.createElement('textarea')
        textarea.value = message.content
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1200)
    } catch (e) {
      console.error('复制失败:', e)
    }
  }

  const renderContent = () => {
    if (!message?.content) return null

    // 当回复包含“是否需要”时，提供可点击的“需要”快捷按钮
    const lines = message.content.split('\n')
    return lines.map((line, index) => {
      const hasNeedPrompt = !isUser && line.includes('是否需要') && typeof onQuickReply === 'function'
      if (hasNeedPrompt) {
        const needIndex = line.indexOf('需要')
        const beforeNeed = line.slice(0, needIndex)
        const afterNeed = line.slice(needIndex + 2)
        return (
          <React.Fragment key={index}>
            {beforeNeed}
            <button
              type="button"
              className="need-action-pill"
              onClick={() => onQuickReply('需要')}
              disabled={optionsDisabled}
              aria-label="回复需要"
            >
              需要
            </button>
            {afterNeed}
            {index < lines.length - 1 && <br />}
          </React.Fragment>
        )
      }

      return (
        <React.Fragment key={index}>
          {line}
          {index < lines.length - 1 && <br />}
        </React.Fragment>
      )
    })
  }

  return (
    <div className={`chat-message ${isUser ? 'user' : 'assistant'}`}>
      {!isUser && (
        <div className="assistant-avatar" aria-hidden="true">
          🤖
        </div>
      )}
      <div className="message-content">
        {!isUser && (
          <div className="message-bubble-icon" aria-hidden="true">
            💡
          </div>
        )}
        {!isUser && (
          <div className="message-actions">
            <button
              type="button"
              className="message-action-btn"
              onClick={copyToClipboard}
              aria-label="复制回答"
              title="复制"
            >
              {copied ? '已复制' : '复制'}
            </button>
            {onQuickAction && (
              <>
                <button
                  type="button"
                  className="message-action-btn"
                  onClick={() => onQuickAction('重新表述需求')}
                  aria-label="重新表述需求"
                  title="重新表述需求"
                >
                  🔄 重述需求
                </button>
                <button
                  type="button"
                  className="message-action-btn"
                  onClick={() => onQuickAction('返回上一步')}
                  aria-label="返回上一步"
                  title="返回上一步"
                >
                  ↶ 返回上一步
                </button>
              </>
            )}
          </div>
        )}
        <div className="message-text">
          {renderContent()}
        </div>
        {message.options && message.options.length > 0 && (
          <div className="message-options">
            <div className="options-list">
              {message.options.map((option, index) => (
                <button
                  key={index}
                  className="option-button"
                  onClick={() => handleOptionClick(option)}
                  disabled={optionsDisabled}
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

