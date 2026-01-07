import React, { useState, useRef, useEffect } from 'react'
import ChatMessage from './components/ChatMessage'
import ChatInput from './components/ChatInput'
import FileList from './components/FileList'
import TypingIndicator from './components/TypingIndicator'
import { sendMessage } from './services/api'
import './App.css'

function App() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: '您好！我是智能车辆电路图资料导航助手。请输入您要查找的电路图关键词，例如：重汽豪沃国六电路图、福田C81电路图'
    }
  ])
  const [isLoading, setIsLoading] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isAtBottom, setIsAtBottom] = useState(true)
  const [hasNewSinceScroll, setHasNewSinceScroll] = useState(false)
  const [files, setFiles] = useState([
    // 初始化已识别的文件
    {
      name: '资料清单.csv',
      size: null,
      uploadTime: '已识别'
    }
  ])
  const messagesEndRef = useRef(null)
  const messagesContainerRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    // 只有在用户位于底部附近时才自动滚动，避免用户回看历史时被强制拉回底部
    if (isAtBottom) {
      scrollToBottom()
    } else {
      setHasNewSinceScroll(true)
    }
  }, [messages])

  useEffect(() => {
    if (isAtBottom) {
      setHasNewSinceScroll(false)
    }
  }, [isAtBottom])

  useEffect(() => {
    // 打开移动端侧栏时，锁定背景滚动
    if (isSidebarOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isSidebarOpen])

  const handleMessagesScroll = () => {
    const el = messagesContainerRef.current
    if (!el) return
    const threshold = 80
    const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight)
    const atBottom = distanceFromBottom < threshold
    setIsAtBottom(atBottom)
  }

  const handleSendMessage = async (content) => {
    if (!content.trim() || isLoading) return

    // 添加用户消息
    const userMessage = { role: 'user', content: content.trim() }
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    // 用户主动发送时，尽量保持在底部
    setIsAtBottom(true)

    try {
      // 调用API
      const response = await sendMessage(content, messages)
      
      // 添加助手回复
      const assistantMessage = {
        role: 'assistant',
        content: response.message,
        results: response.results,
        options: response.options,
        needs_choice: response.needs_choice
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('发送消息失败:', error)
      const errorMessage = {
        role: 'assistant',
        content: '抱歉，发生了错误。请稍后重试。'
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleQuickAction = async (action) => {
    if (isLoading) return

    let messageContent = ''
    let shouldAddUserMessage = true
    if (action === '重新表述需求') {
      messageContent = '我要重述需求'
    } else if (action === '返回上一步') {
      messageContent = '返回上一步'
      // 返回上一步是操作命令，不需要显示用户消息
      shouldAddUserMessage = false
    } else {
      return
    }

    // 对于返回上一步，不添加用户消息（因为这是操作命令，不是对话内容）
    if (shouldAddUserMessage) {
      const userMessage = { role: 'user', content: messageContent }
      setMessages(prev => [...prev, userMessage])
    }
    
    setIsLoading(true)
    setIsAtBottom(true)

    try {
      // 调用API
      const response = await sendMessage(messageContent, messages)

      // 添加助手回复
      const assistantMessage = {
        role: 'assistant',
        content: response.message,
        results: response.results,
        options: response.options,
        needs_choice: response.needs_choice
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('快捷操作失败:', error)
      const errorMessage = {
        role: 'assistant',
        content: '抱歉，操作失败。请稍后重试。'
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUpload = (file) => {
    const newFile = {
      name: file.name,
      size: file.size,
      uploadTime: new Date().toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    }
    setFiles(prev => [...prev, newFile])

    // 这里可以添加文件上传到后端的逻辑
    // 例如：uploadFile(file)
  }

  return (
    <div className="app">
      <div className="app-content">
        <main className="app-main">
          <div className="brand-header">
            <button
              type="button"
              className="sidebar-toggle"
              onClick={() => setIsSidebarOpen(true)}
              aria-label="打开已识别文件侧栏"
              title="已识别文件"
            >
              文件
            </button>
            <h1 className="brand-name">Chatbot</h1>
          </div>
          <div
            className="messages-container"
            ref={messagesContainerRef}
            onScroll={handleMessagesScroll}
          >
            {messages.map((message, index) => (
              <ChatMessage
                key={index}
                message={message}
                onOptionClick={handleSendMessage}
                onQuickAction={handleQuickAction}
                onQuickReply={handleSendMessage}
                optionsDisabled={isLoading}
              />
            ))}
            {isLoading && (
              <TypingIndicator />
            )}
            {!isAtBottom && (
              <button
                type="button"
                className={`scroll-to-bottom ${hasNewSinceScroll ? 'has-new' : ''}`}
                onClick={scrollToBottom}
                aria-label="回到最新消息"
                title="回到最新消息"
              >
                回到底部{hasNewSinceScroll ? ' · 新消息' : ''}
              </button>
            )}
            <div ref={messagesEndRef} />
          </div>
          <ChatInput 
            onSend={handleSendMessage} 
            onFileUpload={handleFileUpload}
            disabled={isLoading} 
          />
        </main>
        {isSidebarOpen && (
          <div
            className="sidebar-backdrop"
            onClick={() => setIsSidebarOpen(false)}
            aria-hidden="true"
          />
        )}
        <aside className={`file-sidebar ${isSidebarOpen ? 'open' : ''}`}>
          <div className="file-sidebar-mobile-header">
            <div className="file-sidebar-title">已识别文件</div>
            <button
              type="button"
              className="file-sidebar-close"
              onClick={() => setIsSidebarOpen(false)}
              aria-label="关闭侧栏"
              title="关闭"
            >
              关闭
            </button>
          </div>
          <FileList files={files} />
        </aside>
      </div>
    </div>
  )
}

export default App

