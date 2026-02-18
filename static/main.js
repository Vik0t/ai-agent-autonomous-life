// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
    // Инициализация тестовых данных
    initializeAgentData();
    
    // Initialize WebSocket connection
    initializeWebSocket();
    
    // Initialize header
    initializeHeader();
    
    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(React.createElement(App));
});

// Initialize WebSocket connection
function initializeWebSocket() {
    // Connect to backend WebSocket
    window.websocketClient.connect();
    
    // Handle world state updates
    window.websocketClient.on('world_state', (worldState) => {
        console.log('Received world state update:', worldState);
        // Update the UI with real agent data
        updateAgentData(worldState.agents);
        updateMessagesFromWebSocket(worldState.recent_messages);
    });
    
    // Handle individual agent messages
    window.websocketClient.on('agent_message', (message) => {
        console.log('Received agent message:', message);
        addAgentMessage(message);
    });
    
    // Handle system events
    window.websocketClient.on('event', (event) => {
        console.log('Received system event:', event);
        addSystemEvent(event);
    });
}

// Глобальное состояние для хранения данных агентов
window.agentsData = [];
window.currentView = 'dashboard';
window.selectedAgent = null;
window.selectedAgents = []; // Для групповых чатов
window.messages = {}; // Для хранения сообщений

// Функция для переключения представления
window.setView = (view, agent = null, agents = null) => {
    window.currentView = view;
    window.selectedAgent = agent;
    window.selectedAgents = agents || [];
    // Перерисовываем приложение
    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(React.createElement(App));
    
    // Update navigation in header
    const navContainer = document.getElementById('nav-container');
    if (navContainer) {
        const navElement = React.createElement(Navigation, {
            currentPage: window.currentView,
            onNavigate: (page) => {
                window.setView(page);
            }
        });
        const navRoot = ReactDOM.createRoot(navContainer);
        navRoot.render(navElement);
    }
};

// Функция для отправки сообщения агенту
window.sendMessageToAgent = async (agentId, content) => {
    try {
        // В реальном приложении здесь будет API вызов
        const message = {
            id: Date.now(),
            sender_id: 'user',
            sender_name: 'Вы',
            content: content,
            timestamp: new Date().toLocaleTimeString()
        };
        
        if (!window.messages[agentId]) {
            window.messages[agentId] = [];
        }
        
        window.messages[agentId].push(message);
        
        // Перерисовываем приложение
        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(React.createElement(App));
    } catch (error) {
        console.error('Ошибка отправки сообщения:', error);
    }
};

// Инициализация тестовых данных агентов
function initializeAgentData() {
    window.agentsData = [
        {
            id: 1,
            name: 'Алексей',
            status: 'online',
            avatar: '🤖',
            role: 'Аналитик',
            department: 'Исследования',
            bio: 'Специалист по анализу данных с 5-летним опытом',
            skills: ['Анализ данных', 'Статистика', 'Python'],
            current_plan: 'Анализ поведения пользователей',
            personality: {
                openness: 0.8,
                conscientiousness: 0.9,
                extraversion: 0.6,
                agreeableness: 0.7,
                neuroticism: 0.3
            },
            emotions: {
                happiness: 0.7,
                sadness: 0.1,
                anger: 0.05,
                fear: 0.05,
                surprise: 0.1,
                disgust: 0.0
            },
            relationships: {
                2: { familiarity: 0.8, affinity: 0.7 },
                3: { familiarity: 0.6, affinity: 0.5 }
            },
            memories: [
                {
                    content: 'Обсуждал проект с Марией',
                    timestamp: new Date(Date.now() - 3600000).toISOString(),
                    emotions: { happiness: 0.8, surprise: 0.2 }
                },
                {
                    content: 'Завершил анализ данных',
                    timestamp: new Date(Date.now() - 7200000).toISOString(),
                    emotions: { happiness: 0.9, pride: 0.7 }
                }
            ],
            memory_count: 24
        },
        {
            id: 2,
            name: 'Мария',
            status: 'busy',
            avatar: '👾',
            role: 'Дизайнер',
            department: 'Креатив',
            bio: 'UX/UI дизайнер с фокусом на пользовательский опыт',
            skills: ['Figma', 'UI/UX', 'Прототипирование'],
            current_plan: 'Создание нового интерфейса',
            personality: {
                openness: 0.9,
                conscientiousness: 0.7,
                extraversion: 0.8,
                agreeableness: 0.9,
                neuroticism: 0.2
            },
            emotions: {
                happiness: 0.6,
                sadness: 0.1,
                anger: 0.05,
                fear: 0.1,
                surprise: 0.15,
                disgust: 0.0
            },
            relationships: {
                1: { familiarity: 0.8, affinity: 0.7 },
                3: { familiarity: 0.9, affinity: 0.8 }
            },
            memories: [
                {
                    content: 'Работала над новым дизайном',
                    timestamp: new Date(Date.now() - 1800000).toISOString(),
                    emotions: { happiness: 0.7, creativity: 0.8 }
                },
                {
                    content: 'Обсуждала идеи с Алексеем',
                    timestamp: new Date(Date.now() - 5400000).toISOString(),
                    emotions: { happiness: 0.8, collaboration: 0.7 }
                }
            ],
            memory_count: 32
        },
        {
            id: 3,
            name: 'Дмитрий',
            status: 'offline',
            avatar: '🦾',
            role: 'Разработчик',
            department: 'Технологии',
            bio: 'Full-stack разработчик специализирующийся на React и Node.js',
            skills: ['JavaScript', 'React', 'Node.js', 'MongoDB'],
            current_plan: 'Оптимизация кода',
            personality: {
                openness: 0.7,
                conscientiousness: 0.8,
                extraversion: 0.5,
                agreeableness: 0.6,
                neuroticism: 0.4
            },
            emotions: {
                happiness: 0.5,
                sadness: 0.2,
                anger: 0.1,
                fear: 0.15,
                surprise: 0.05,
                disgust: 0.0
            },
            relationships: {
                1: { familiarity: 0.6, affinity: 0.5 },
                2: { familiarity: 0.9, affinity: 0.8 }
            },
            memories: [
                {
                    content: 'Исправил критическую ошибку',
                    timestamp: new Date(Date.now() - 10800000).toISOString(),
                    emotions: { relief: 0.8, pride: 0.7 }
                },
                {
                    content: 'Обсуждал архитектуру с Марией',
                    timestamp: new Date(Date.now() - 14400000).toISOString(),
                    emotions: { happiness: 0.6, collaboration: 0.6 }
                }
            ],
            memory_count: 41
        }
    ];
    
    // Инициализируем сообщения
    window.messages = {
        1: [
            {
                id: 1,
                sender_id: 1,
                sender_name: 'Алексей',
                content: 'Привет! Я готов помочь с анализом данных.',
                timestamp: new Date(Date.now() - 3600000).toLocaleTimeString()
            }
        ],
        2: [
            {
                id: 2,
                sender_id: 2,
                sender_name: 'Мария',
                content: 'Здравствуйте! Я могу помочь с дизайном интерфейса.',
                timestamp: new Date(Date.now() - 7200000).toLocaleTimeString()
            }
        ],
        3: [
            {
                id: 3,
                sender_id: 3,
                sender_name: 'Дмитрий',
                content: 'Привет! У меня есть идеи для нового функционала.',
                timestamp: new Date(Date.now() - 10800000).toLocaleTimeString()
            }
        ]
    };
}

// Update agent data from WebSocket
function updateAgentData(agents) {
    if (agents && Array.isArray(agents)) {
        window.agentsData = agents.map(agent => ({
            id: agent.id,
            name: agent.name,
            status: 'online',
            avatar: getAgentAvatar(agent.name),
            role: 'AI Agent',
            department: 'Virtual',
            bio: `AI Agent with personality traits: Openness ${agent.personality?.openness || 0.5},
                  Conscientiousness ${agent.personality?.conscientiousness || 0.5}`,
            skills: ['Communication', 'Social Interaction'],
            current_plan: agent.current_plan || 'Thinking...',
            personality: agent.personality || {
                openness: 0.5,
                conscientiousness: 0.5,
                extraversion: 0.5,
                agreeableness: 0.5,
                neuroticism: 0.5
            },
            emotions: agent.emotions || {
                happiness: 0.5,
                sadness: 0.0,
                anger: 0.0,
                fear: 0.0,
                surprise: 0.0,
                disgust: 0.0
            },
            relationships: agent.relationships || {},
            memories: agent.memories || [],
            memory_count: agent.memory_count || 0
        }));
        
        // Refresh the UI if we're on the agents view
        if (window.currentView === 'agents' || window.currentView === 'group-chat') {
            const root = ReactDOM.createRoot(document.getElementById('root'));
            root.render(React.createElement(App));
        }
    }
}

// Update messages from WebSocket
function updateMessagesFromWebSocket(recentMessages) {
    if (recentMessages && Array.isArray(recentMessages)) {
        // Convert backend messages to frontend format
        recentMessages.forEach(msg => {
            const frontendMessage = {
                id: msg.id || Date.now() + Math.random(),
                sender_id: msg.sender_id,
                receiver_id: msg.receiver_id,
                content: msg.content,
                timestamp: new Date(msg.timestamp * 1000).toLocaleTimeString(),
                is_user: false
            };
            
            // Add to global messages
            if (!window.messages[msg.sender_id]) {
                window.messages[msg.sender_id] = [];
            }
            
            // Check if message already exists
            const exists = window.messages[msg.sender_id].some(m => m.id === frontendMessage.id);
            if (!exists) {
                window.messages[msg.sender_id].push(frontendMessage);
                
                // Refresh UI if we're on the chat view
                if (window.currentView === 'chat' || window.currentView === 'group-chat') {
                    const root = ReactDOM.createRoot(document.getElementById('root'));
                    root.render(React.createElement(App));
                }
            }
        });
    }
}

// Add individual agent message
function addAgentMessage(message) {
    // Find sender agent
    const senderAgent = window.agentsData.find(agent => agent.id === message.sender_id);
    const senderName = senderAgent ? senderAgent.name : `Agent ${message.sender_id}`;
    
    const frontendMessage = {
        id: Date.now() + Math.random(),
        sender_id: message.sender_id,
        sender_name: senderName,
        content: message.content,
        timestamp: new Date().toLocaleTimeString(),
        is_user: false
    };
    
    // Add to global messages
    if (!window.messages[message.sender_id]) {
        window.messages[message.sender_id] = [];
    }
    
    window.messages[message.sender_id].push(frontendMessage);
    
    // Refresh UI if we're on the chat view or specific agent chat
    if (window.currentView === 'chat' ||
        (window.currentView === 'agent' && window.selectedAgent && window.selectedAgent.id == message.sender_id) ||
        (window.currentView === 'group-chat' && window.selectedAgents.some(agent => agent.id == message.sender_id))) {
        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(React.createElement(App));
    }
}

// Add system event
function addSystemEvent(event) {
    // For now, we'll just log it
    console.log('System event:', event);
}

// Get agent avatar based on name
function getAgentAvatar(name) {
    const avatars = ['🤖', '👾', '🦾', '👽', '👻', '🧠', '💻', '📱'];
    const index = name.charCodeAt(0) % avatars.length;
    return avatars[index];
}

// Initialize header with title and navigation
function initializeHeader() {
    // Create title element
    const titleContainer = document.getElementById('title-container');
    if (titleContainer) {
        const title = document.createElement('h1');
        title.className = 'glitch-text';
        title.setAttribute('data-text', 'КИБЕР РЫВОК');
        title.textContent = 'КИБЕР РЫВОК';
        titleContainer.appendChild(title);
        
        const subtitle = document.createElement('p');
        subtitle.textContent = 'Симулятор AI-Агентов';
        titleContainer.appendChild(subtitle);
    }
    
    // Create navigation element
    const navContainer = document.getElementById('nav-container');
    if (navContainer) {
        const navElement = React.createElement(Navigation, {
            currentPage: window.currentView,
            onNavigate: (page) => {
                window.setView(page);
            }
        });
        const navRoot = ReactDOM.createRoot(navContainer);
        navRoot.render(navElement);
    }
}