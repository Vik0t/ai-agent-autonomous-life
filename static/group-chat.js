// Group Chat Component
const GroupChat = ({ agents, onBack, onSendMessage }) => {
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
        if (agents && agents.length > 0) {
            setIsLoading(true);
            // Simulate API call to fetch chat history
            setTimeout(() => {
                const mockMessages = [
                    {
                        id: '1',
                        sender_id: agents[0].id,
                        sender_name: agents[0].name,
                        content: 'Привет всем! Как дела?',
                        timestamp: '10:30'
                    },
                    {
                        id: '2',
                        sender_id: agents[1].id,
                        sender_name: agents[1].name,
                        content: 'Привет! У меня всё хорошо. Как продвигается проект?',
                        timestamp: '10:32'
                    },
                    {
                        id: '3',
                        sender_id: 'user',
                        sender_name: 'Вы',
                        content: 'Отлично! Мы работаем над новыми функциями для симуляции.',
                        timestamp: '10:35'
                    },
                    {
                        id: '4',
                        sender_id: agents[2].id,
                        sender_name: agents[2].name,
                        content: 'Это звучит интересно! Расскажите подробнее.',
                        timestamp: '10:37'
                    }
                ];
                setMessages(mockMessages);
                setIsLoading(false);
            }, 500);
        }
    }, [agents]);

    // Handle sending a message
    const handleSendMessage = () => {
        if (newMessage.trim() && agents) {
            const message = {
                id: Date.now().toString(),
                sender_id: 'user',
                sender_name: 'Вы',
                content: newMessage,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
            
            setMessages(prev => [...prev, message]);
            setNewMessage('');
            
            // Simulate agent responses
            setTimeout(() => {
                if (agents.length > 0) {
                    const randomAgent = agents[Math.floor(Math.random() * agents.length)];
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
                        sender_id: randomAgent.id,
                        sender_name: randomAgent.name,
                        content: responses[Math.floor(Math.random() * responses.length)],
                        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    };
                    
                    setMessages(prev => [...prev, response]);
                }
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

    if (!agents || agents.length === 0) {
        return React.createElement('div', { className: 'container' },
            React.createElement('div', { className: 'panel' },
                React.createElement('h2', null, 'Агенты не найдены')
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
            React.createElement('div', { className: 'chat-group-info' },
                React.createElement('div', { className: 'chat-group-avatars' },
                    agents.slice(0, 3).map(agent => 
                        React.createElement('div', {
                            key: agent.id,
                            className: 'chat-group-avatar',
                            title: agent.name
                        }, agent.avatar)
                    ),
                    agents.length > 3 && React.createElement('div', {
                        className: 'chat-group-avatar more'
                    }, `+${agents.length - 3}`)
                ),
                React.createElement('div', { className: 'chat-group-details' },
                    React.createElement('h2', null, 'Групповой чат'),
                    React.createElement('p', null, `${agents.length} участников`)
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
                            className: `message ${msg.sender_id === 'user' ? 'user-message' : 'agent-message'}`
                        },
                            React.createElement('div', { className: 'message-header' },
                                React.createElement('span', { className: 'message-sender' }, msg.sender_name),
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
                placeholder: 'Сообщение в группу...',
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
const addGroupChatStyles = () => {
    const style = document.createElement('style');
    style.textContent = `
        .chat-group-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .chat-group-avatars {
            display: flex;
            gap: -10px;
        }
        
        .chat-group-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
            box-shadow: 0 0 10px rgba(0, 240, 255, 0.3);
            border: 2px solid var(--dark-bg);
            z-index: 1;
        }
        
        .chat-group-avatar.more {
            background: linear-gradient(135deg, var(--neon-purple), #ff0040);
            font-size: 0.8rem;
        }
        
        .chat-group-details h2 {
            margin: 0 0 5px 0;
            font-size: 1.5rem;
        }
        
        .chat-group-details p {
            margin: 0;
            color: rgba(255, 255, 255, 0.7);
            font-size: 0.9rem;
        }
    `;
    document.head.appendChild(style);
};

// Add styles when the file loads
addGroupChatStyles();