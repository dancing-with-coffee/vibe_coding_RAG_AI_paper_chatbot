import React, { useState, useRef, useEffect } from 'react'
import './App.css'

interface Message {
  id: number
  text: string
  isUser: boolean
  sources?: Array<{
    filename: string
    relevance_score: number
  }>
}

interface ChatResponse {
  answer: string
  sources: Array<{
    filename: string
    relevance_score: number
  }>
}

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      text: "안녕하세요! AI 연구 논문에 대해 궁금한 것이 있으시면 언제든 물어보세요. 📚",
      isUser: false
    }
  ])
  const [inputText, setInputText] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async () => {
    if (!inputText.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now(),
      text: inputText,
      isUser: true
    }

    setMessages(prev => [...prev, userMessage])
    setInputText('')
    setIsLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: inputText }),
      })

      if (!response.ok) {
        throw new Error('서버 응답 오류')
      }

      const data: ChatResponse = await response.json()

      const botMessage: Message = {
        id: Date.now() + 1,
        text: data.answer,
        isUser: false,
        sources: data.sources
      }

      setMessages(prev => [...prev, botMessage])
    } catch (error) {
      const errorMessage: Message = {
        id: Date.now() + 1,
        text: '죄송합니다. 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
        isUser: false
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="app">
      <div className="header">
        <h1>🤖 AI Research Papers RAG Chatbot</h1>
        <p>AI 연구 논문에 대해 궁금한 것을 물어보세요</p>
      </div>

      <div className="chat-container">
        <div className="messages">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`message ${message.isUser ? 'user' : 'bot'}`}
            >
              <div className="message-content">
                <div className="message-text">{message.text}</div>
                {message.sources && message.sources.length > 0 && (
                  <div className="sources">
                    <div className="sources-title">📖 참고 논문:</div>
                    {message.sources.map((source, index) => (
                      <div key={index} className="source-item">
                        • {source.filename.replace('.pdf', '')} 
                        <span className="relevance">({Math.round(source.relevance_score * 100)}% 관련성)</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message bot">
              <div className="message-content">
                <div className="loading">답변을 생성하고 있습니다...</div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-container">
          <div className="input-wrapper">
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="AI 연구 논문에 대해 질문해보세요..."
              disabled={isLoading}
              rows={1}
            />
            <button 
              onClick={sendMessage} 
              disabled={!inputText.trim() || isLoading}
              className="send-button"
            >
              {isLoading ? '⏳' : '🚀'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
