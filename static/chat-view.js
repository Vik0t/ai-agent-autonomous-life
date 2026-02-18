// Chat View Component - Shows all agent messages in one place
const ChatView = ({ onBack }) => {
    const [messages, setMessages] = React.useState([]);
    const [isLoading, setIsLoading] = React.useState(true);
    
    // Load all messages from window.messages
    React.useEffect(() => {
        // Load messages immediately
        loadMessages();
        
        // Set up listener for new messages
        const handleNewMessage = (message) => {
            setMessages(prev => {
                // Convert backend message to frontend format
                const agent = window.agentsData?.find(a => a.id == message.sender_id);
                const newMessage = {
                    id: message.id || Date.now() + Math.random(),
                    sender_id: message.sender_id,
                    sender_name: agent ? agent.name : `Agent ${message.sender_id}`,
                    content: message.content,
                    timestamp: new Date().toLocaleTimeString(),
                    is_system: false,
                    agentAvatar: agent ? agent.avatar : '🤖'
                };
                
                // Check if message already exists
                const exists = prev.some(m => m.id === newMessage.id);
                if (!exists) {
                    return [...prev, newMessage].sort((a, b) => {
                        return a.timestamp.localeCompare(b.timestamp);
                    });
                }
                return prev;
            });
        };
        
        const handleWorldState = (worldState) => {
            if (worldState.recent_messages) {
                loadMessages();
            }
        };
        
        window.websocketClient.on('agent_message', handleNewMessage);
        window.websocketClient.on('world_state', handleWorldState);
        
        // Clean up listeners
        return () => {
            window.websocketClient.off('agent_message', handleNewMessage);
            window.websocketClient.off('world_state', handleWorldState);
        };
    }, []);
    
    const loadMessages = () => {
        setIsLoading(true);
        // Collect all messages from all agents
        const allMessages = [];
        
        // Get messages from window.messages if available
        if (window.messages) {
            Object.entries(window.messages).forEach(([agentId, agentMessages]) => {
                agentMessages.forEach(msg => {
                    // Find agent name
                    const agent = window.agentsData?.find(a => a.id == agentId);
                    allMessages.push({
                        ...msg,
                        agentName: agent ? agent.name : `Агент ${agentId}`,
                        agentAvatar: agent ? agent.avatar : '🤖'
                    });
                });
            });
        }
        
        // Add some mock system messages
        const systemMessages = [
            {
                id: 'sys1',
                sender_id: 'system',
                sender_name: 'Система',
                content: 'Система инициализирована. Агенты активированы.',
                timestamp: '09:00',
                is_system: true
            },
            {
                id: 'sys2',
                sender_id: 'system',
                sender_name: 'Система',
                content: 'Начало симуляции взаимодействий агентов',
                timestamp: '09:05',
                is_system: true
            }
        ];
        
        // Combine and sort by timestamp
        const combinedMessages = [...systemMessages, ...allMessages];
        combinedMessages.sort((a, b) => {
            // Simple sorting by timestamp string
            return a.timestamp.localeCompare(b.timestamp);
        });
        
        setMessages(combinedMessages);
        setIsLoading(false);
    };
    
    return React.createElement('div', { className: 'container chat-view-container' },
        // Header
        React.createElement('div', { className: 'chat-view-header' },
            React.createElement('button', {
                className: 'cyber-btn secondary back-button',
                onClick: onBack
            }, '← Назад'),
            React.createElement('h1', null, 'Общий чат агентов')
        ),
        
        // Messages container
        React.createElement('div', { className: 'chat-view-messages' },
            isLoading ? 
                React.createElement('div', { className: 'loading-messages' },
                    React.createElement('div', { className: 'loading-spinner' }),
                    React.createElement('p', null, 'Загрузка сообщений...')
                ) :
                React.createElement('div', { className: 'messages-list' },
                    messages.map(msg => 
                        React.createElement('div', {
                            key: msg.id,
                            className: `message ${msg.is_system ? 'system-message' : msg.sender_id === 'user' ? 'user-message' : 'agent-message'}`
                        },
                            React.createElement('div', { className: 'message-header' },
                                !msg.is_system && React.createElement('span', { className: 'message-avatar' }, 
                                    msg.agentAvatar || '🤖'
                                ),
                                React.createElement('span', { className: 'message-sender' }, 
                                    msg.sender_name || msg.agentName || 'Неизвестный'
                                ),
                                React.createElement('span', { className: 'message-time' }, msg.timestamp)
                            ),
                            React.createElement('div', { className: 'message-content' }, msg.content)
                        )
                    )
                )
        )
    );
};

// Add to global styles
const addChatViewStyles = () => {
    const style = document.createElement('style');
    style.textContent = `
        .chat-view-container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .chat-view-header {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .chat-view-messages {
            height: 600px;
            overflow-y: auto;
            padding: 20px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 12px;
            border: 1px solid rgba(0, 240, 255, 0.1);
        }
        
        .chat-view-messages .message {
            margin-bottom: 20px;
            padding: 15px;
            border-radius: 12px;
            animation: fadeIn 0.3s ease;
        }
        
        .chat-view-messages .system-message {
            background: rgba(255, 238, 0, 0.1);
            border: 1px solid rgba(255, 238, 0, 0.3);
        }
        
        .chat-view-messages .user-message {
            background: rgba(0, 240, 255, 0.1);
            border: 1px solid rgba(0, 240, 255, 0.3);
            margin-left: 50px;
        }
        
        .chat-view-messages .agent-message {
            background: rgba(184, 41, 221, 0.1);
            border: 1px solid rgba(184, 41, 221, 0.3);
            margin-right: 50px;
        }
        
        .message-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
        }
        
        .message-avatar {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
        }
        
        .message-sender {
            font-weight: 700;
            color: var(--neon-cyan);
        }
        
        .system-message .message-sender {
            color: var(--neon-yellow);
        }
        
        .message-time {
            color: rgba(255, 255, 255, 0.5);
            font-size: 0.8rem;
        }
        
        .message-content {
            font-size: 1rem;
            line-height: 1.5;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @media (max-width: 768px) {
            .chat-view-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .chat-view-messages {
                height: 500px;
            }
            
            .chat-view-messages .user-message {
                margin-left: 0;
            }
            
            .chat-view-messages .agent-message {
                margin-right: 0;
            }
        }
    `;
    document.head.appendChild(style);
};

// Add styles when the file loads
addChatViewStyles();