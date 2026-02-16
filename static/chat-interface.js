// Chat Interface Component
const ChatInterface = ({ agent, onBack, onSendMessage }) => {
    const [messages, setMessages] = React.useState([]);
    const [newMessage, setNewMessage] = React.useState('');
    const [isLoading, setIsLoading] = React.useState(false);
    const messagesEndRef = React.useRef(null);

    // Scroll to bottom of messages
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    React.useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Simulate loading chat history
    React.useEffect(() => {
        if (agent) {
            setIsLoading(true);
            // Simulate API call to fetch chat history
            setTimeout(() => {
                const mockMessages = [
                    {
                        id: '1',
                        sender_id: 'user',
                        receiver_id: agent.id,
                        content: 'Привет! Как дела?',
                        timestamp: '10:30',
                        is_user: true
                    },
                    {
                        id: '2',
                        sender_id: agent.id,
                        receiver_id: 'user',
                        content: `Привет! У меня всё хорошо, спасибо за спрос. Я ${agent.name}, и я рад общаться с тобой!`,
                        timestamp: '10:32',
                        is_user: false
                    },
                    {
                        id: '3',
                        sender_id: 'user',
                        receiver_id: agent.id,
                        content: 'Отлично! Мы работаем над новыми функциями для симуляции.',
                        timestamp: '10:35',
                        is_user: true
                    },
                    {
                        id: '4',
                        sender_id: agent.id,
                        receiver_id: 'user',
                        content: 'Это звучит интересно! Расскажи подробнее о проекте.',
                        timestamp: '10:37',
                        is_user: false
                    }
                ];
                setMessages(mockMessages);
                setIsLoading(false);
            }, 500);
        }
    }, [agent]);

    // Handle sending a message
    const handleSendMessage = () => {
        if (newMessage.trim() && agent) {
            const message = {
                id: Date.now().toString(),
                sender_id: 'user',
                receiver_id: agent.id,
                content: newMessage,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                is_user: true
            };
            
            setMessages(prev => [...prev, message]);
            setNewMessage('');
            
            // Simulate agent response
            setTimeout(() => {
                const responses = [
                    "Интересная мысль! Давай обсудим подробнее.",
                    "Я согласен с твоей точкой зрения.",
                    "Не уверен, что это правильный подход.",
                    "Это напоминает мне прошлое событие...",
                    "Давайте работать вместе над этим!",
                    "Мне нужно время обдумать это.",
                    "Звучит интригующе! Расскажи больше."
                ];
                
                const response = {
                    id: (Date.now() + 1).toString(),
                    sender_id: agent.id,
                    receiver_id: 'user',
                    content: responses[Math.floor(Math.random() * responses.length)],
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    is_user: false
                };
                
                setMessages(prev => [...prev, response]);
            }, 1000 + Math.random() * 2000);
        }
    };

    // Handle key press (Enter to send)
    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    if (!agent) {
        return React.createElement('div', { className: 'container' },
            React.createElement('div', { className: 'panel' },
                React.createElement('h2', null, 'Агент не найден')
            )
        );
    }

    return React.createElement('div', { className: 'container chat-container' },
        // Chat header
        React.createElement('div', { className: 'chat-header' },
            React.createElement('button', {
                className: 'cyber-btn secondary back-button',
                onClick: onBack
            }, '← Назад'),
            React.createElement('div', { className: 'chat-agent-info' },
                React.createElement('div', { className: 'chat-agent-avatar' }, agent.avatar),
                React.createElement('div', { className: 'chat-agent-details' },
                    React.createElement('h2', null, agent.name),
                    React.createElement('p', null, agent.current_plan || 'Активен')
                )
            )
        ),
        
        // Messages container
        React.createElement('div', { className: 'messages-container' },
            isLoading ? 
                React.createElement('div', { className: 'loading-messages' },
                    React.createElement('div', { className: 'loading-spinner' }),
                    React.createElement('p', null, 'Загрузка сообщений...')
                ) :
                React.createElement('div', { className: 'messages-list' },
                    messages.map(msg => 
                        React.createElement('div', {
                            key: msg.id,
                            className: `message ${msg.is_user ? 'user-message' : 'agent-message'}`
                        },
                            React.createElement('div', { className: 'message-header' },
                                React.createElement('span', { className: 'message-sender' }, 
                                    msg.is_user ? 'Вы' : agent.name
                                ),
                                React.createElement('span', { className: 'message-time' }, msg.timestamp)
                            ),
                            React.createElement('div', { className: 'message-content' }, msg.content)
                        )
                    ),
                    React.createElement('div', { ref: messagesEndRef })
                )
        ),
        
        // Message input
        React.createElement('div', { className: 'message-input-area' },
            React.createElement('textarea', {
                className: 'cyber-input',
                placeholder: `Сообщение ${agent.name}...`,
                value: newMessage,
                onChange: (e) => setNewMessage(e.target.value),
                onKeyPress: handleKeyPress,
                rows: 3
            }),
            React.createElement('button', {
                className: 'cyber-btn send-button',
                onClick: handleSendMessage,
                disabled: !newMessage.trim()
            }, 'Отправить')
        )
    );
};

// Add to global styles
const addChatInterfaceStyles = () => {
    const style = document.createElement('style');
    style.textContent = `
        .chat-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .chat-header {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 12px;
            border: 1px solid rgba(0, 240, 255, 0.1);
        }
        
        .back-button {
            margin-right: 10px;
        }
        
        .chat-agent-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .chat-agent-avatar {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
            box-shadow: 0 0 20px rgba(0, 240, 255, 0.3);
        }
        
        .chat-agent-details h2 {
            margin: 0 0 5px 0;
            font-size: 1.5rem;
        }
        
        .chat-agent-details p {
            margin: 0;
            color: rgba(255, 255, 255, 0.7);
            font-size: 0.9rem;
        }
        
        .messages-container {
            height: 500px;
            overflow-y: auto;
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            border: 1px solid rgba(0, 240, 255, 0.1);
        }
        
        .loading-messages {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
        }
        
        .messages-list {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .message {
            max-width: 80%;
            padding: 15px;
            border-radius: 12px;
            animation: fadeIn 0.3s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .user-message {
            align-self: flex-end;
            background: linear-gradient(135deg, rgba(0, 240, 255, 0.2), rgba(0, 240, 255, 0.1));
            border: 1px solid rgba(0, 240, 255, 0.3);
            margin-left: auto;
        }
        
        .agent-message {
            align-self: flex-start;
            background: linear-gradient(135deg, rgba(184, 41, 221, 0.2), rgba(184, 41, 221, 0.1));
            border: 1px solid rgba(184, 41, 221, 0.3);
            margin-right: auto;
        }
        
        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.8rem;
        }
        
        .message-sender {
            font-weight: 700;
            color: var(--neon-cyan);
        }
        
        .message-time {
            color: rgba(255, 255, 255, 0.5);
        }
        
        .message-content {
            font-size: 1rem;
            line-height: 1.5;
        }
        
        .message-input-area {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .message-input-area textarea {
            resize: none;
            min-height: 80px;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .send-button {
            align-self: flex-end;
            width: auto;
            padding: 10px 20px;
        }
        
        @media (max-width: 768px) {
            .chat-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .message {
                max-width: 90%;
            }
            
            .messages-container {
                height: 400px;
            }
        }
    `;
    document.head.appendChild(style);
};

// Add styles when the file loads
addChatInterfaceStyles();