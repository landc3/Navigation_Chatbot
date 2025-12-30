import React, { useState, useRef, useEffect } from 'react'
import ChatMessage from './components/ChatMessage'
import ChatInput from './components/ChatInput'
import { sendMessage } from './services/api'
import './App.css'

function App() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: '您好！我是智能车辆电路图资料导航助手。请输入您要查找的电路图关键词，例如：东风天龙仪表针脚图'
    }
  ])
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async (content) => {
    if (!content.trim() || isLoading) return

    // 添加用户消息
    const userMessage = { role: 'user', content: content.trim() }
    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)

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

  return (
    <div className="app">
      <header className="app-header">
        <h1>智能车辆电路图资料导航 Chatbot</h1>
      </header>
      <main className="app-main">
        <div className="messages-container">
          {messages.map((message, index) => (
            <ChatMessage 
              key={index} 
              message={message} 
              onOptionClick={handleSendMessage}
            />
          ))}
          {isLoading && (
            <div className="loading-indicator">
              <span>正在思考...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <ChatInput onSend={handleSendMessage} disabled={isLoading} />
      </main>
    </div>
  )
}

export default App

