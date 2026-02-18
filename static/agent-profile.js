// Agent Profile Page Component
const AgentProfile = ({ agent, onBack, onSendMessage }) => {
    const [activeTab, setActiveTab] = React.useState('chat');

    if (!agent) {
        return React.createElement('div', { className: 'container' },
            React.createElement('div', { className: 'panel' },
                React.createElement('h2', null, 'Агент не найден')
            )
        );
    }

    // Get agent relationships with names
    const relationshipsWithNames = Object.entries(agent.relationships || {}).map(([id, rel]) => {
        const relatedAgent = window.agentsData?.find(a => a.id === id);
        return {
            id,
            name: relatedAgent ? relatedAgent.name : `Агент ${id}`,
            relationship: rel
        };
    });

    // Sort relationships by affinity
    const sortedRelationships = relationshipsWithNames.sort((a, b) => 
        b.relationship.affinity - a.relationship.affinity
    );

    // Get recent memories
    const recentMemories = [...(agent.memories || [])].sort((a, b) => 
        new Date(b.timestamp) - new Date(a.timestamp)
    ).slice(0, 10);

    // Render relationship item
    const renderRelationshipItem = (rel) => {
        const affinityColor = rel.relationship.affinity > 0 ? 
            '#00ff88' : rel.relationship.affinity < 0 ? '#ff0040' : '#ffee00';
        
        return React.createElement('div', { className: 'relationship-item' },
            React.createElement('div', { className: 'rel-agent' },
                React.createElement('div', { className: 'rel-avatar' }, '👤'),
                React.createElement('div', { className: 'rel-info' },
                    React.createElement('div', { className: 'rel-name' }, rel.name),
                    React.createElement('div', { className: 'rel-status' }, 
                        `Знакомство: ${(rel.relationship.familiarity * 100).toFixed(0)}%`
                    )
                )
            ),
            React.createElement('div', {
                className: `rel-affinity ${rel.relationship.affinity > 0 ? 'positive' : rel.relationship.affinity < 0 ? 'negative' : 'neutral'}`
            }, `${rel.relationship.affinity > 0 ? '+' : ''}${rel.relationship.affinity.toFixed(2)}`)
        );
    };

    // Render memory item
    const renderMemoryItem = (memory) => {
        return React.createElement('div', { className: 'memory-item' },
            React.createElement('div', { className: 'memory-time' }, 
                new Date(memory.timestamp).toLocaleString()
            ),
            React.createElement('div', { className: 'memory-content' }, memory.content),
            React.createElement('div', { className: 'memory-emotions' },
                Object.entries(memory.emotions || {}).map(([emotion, value]) => 
                    value > 0.1 ? React.createElement('span', {
                        key: emotion,
                        className: 'emotion-tag',
                        style: { color: emotionColors[emotion] || '#fff' }
                    }, `${emotionTranslations[emotion] || emotion}: ${(value * 100).toFixed(0)}%`) : null
                )
            )
        );
    };

    return React.createElement('div', { className: 'container' },
        // Back button
        React.createElement('div', { className: 'back-button-container' },
            React.createElement('button', {
                className: 'cyber-btn secondary',
                onClick: onBack
            }, '← Назад к списку агентов')
        ),
        
        // Agent header
        React.createElement('div', { className: 'agent-header' },
            React.createElement('div', { className: 'agent-profile-avatar' },
                agent.avatar
            ),
            React.createElement('div', { className: 'agent-profile-info' },
                React.createElement('h1', null, agent.name),
                React.createElement('div', { className: 'agent-status' },
                    React.createElement('span', { className: 'status-dot' }),
                    React.createElement('span', null, agent.current_plan || 'Активен')
                )
            )
        ),
        
        // Tabs
        React.createElement('div', { className: 'tabs' },
            React.createElement('button', {
                className: `tab ${activeTab === 'chat' ? 'active' : ''}`,
                onClick: () => setActiveTab('chat')
            }, 'Чат'),
            React.createElement('button', {
                className: `tab ${activeTab === 'relationships' ? 'active' : ''}`,
                onClick: () => setActiveTab('relationships')
            }, 'Отношения'),
            React.createElement('button', {
                className: `tab ${activeTab === 'memories' ? 'active' : ''}`,
                onClick: () => setActiveTab('memories')
            }, 'Воспоминания')
        ),
        
        // Tab content
        React.createElement('div', { className: 'tab-content' },
            activeTab === 'chat' && React.createElement('div', { className: 'chat-tab' },
                React.createElement(ChatInterface, {
                    agent: agent,
                    onBack: () => {},
                    onSendMessage: (agentId, content) => {
                        onSendMessage(agentId, content);
                    }
                })
            ),
            
            activeTab === 'relationships' && React.createElement('div', { className: 'relationships-tab' },
                React.createElement('h3', null, 'Отношения с другими агентами'),
                React.createElement('div', { className: 'relationship-list' },
                    sortedRelationships.length > 0 ? 
                        sortedRelationships.map(renderRelationshipItem) :
                        React.createElement('p', { className: 'empty-state' }, 'Нет установленных отношений')
                )
            ),
            
            activeTab === 'memories' && React.createElement('div', { className: 'memories-tab' },
                React.createElement('h3', null, 'Последние воспоминания'),
                React.createElement('div', { className: 'memory-list' },
                    recentMemories.length > 0 ? 
                        recentMemories.map(renderMemoryItem) :
                        React.createElement('p', { className: 'empty-state' }, 'Нет воспоминаний')
                )
            )
        )
    );
};

// Add to global styles
const addAgentProfileStyles = () => {
    const style = document.createElement('style');
    style.textContent = `
        .agent-header {
            display: flex;
            align-items: center;
            gap: 24px;
            margin-bottom: 32px;
            padding: 24px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 12px;
            border: 1px solid rgba(0, 240, 255, 0.1);
            overflow: visible;
        }
        
        .agent-profile-avatar {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 3rem;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
            box-shadow: 0 0 30px rgba(0, 240, 255, 0.3);
        }
        
        .agent-profile-info h1 {
            font-size: 2.5rem;
            margin-bottom: 12px;
            color: #fff;
        }
        
        .tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 24px;
            border-bottom: 1px solid rgba(0, 240, 255, 0.2);
            padding-bottom: 12px;
        }
        
        .tab {
            padding: 12px 24px;
            background: transparent;
            border: 1px solid rgba(0, 240, 255, 0.2);
            border-radius: 8px;
            color: rgba(255, 255, 255, 0.7);
            font-family: 'JetBrains Mono', monospace;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .tab:hover {
            background: rgba(0, 240, 255, 0.1);
            color: #fff;
        }
        
        .tab.active {
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
            color: #000;
            border-color: var(--neon-cyan);
        }
        
        .tab-content {
            min-height: 400px;
            overflow: visible;
        }
        
        .chat-messages {
            height: 400px;
            overflow-y: auto;
            padding: 16px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            margin-bottom: 24px;
            border: 1px solid rgba(0, 240, 255, 0.1);
        }
        
        .message {
            margin-bottom: 16px;
            padding: 16px;
            border-radius: 12px;
            max-width: 80%;
        }
        
        .user-message {
            background: rgba(0, 240, 255, 0.1);
            border: 1px solid rgba(0, 240, 255, 0.3);
            margin-left: auto;
        }
        
        .agent-message {
            background: rgba(184, 41, 221, 0.1);
            border: 1px solid rgba(184, 41, 221, 0.3);
            margin-right: auto;
        }
        
        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.85rem;
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
        
        .message-input-container {
            display: flex;
            gap: 12px;
        }
        
        .message-input-container .cyber-input {
            flex: 1;
        }
        
        .relationship-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .memory-list {
            display: flex;
            flex-direction: column;
            gap: 16px;
            max-height: none;
        }
        
        .memory-item {
            padding: 16px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            word-break: break-word;
        }
        
        .memory-time {
            font-size: 0.8rem;
            color: var(--neon-purple);
            margin-bottom: 8px;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .memory-content {
            margin-bottom: 12px;
            line-height: 1.5;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        
        .memory-emotions {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
        
        .emotion-tag {
            font-size: 0.8rem;
            padding: 4px 8px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }
        
        .back-button-container {
            margin-bottom: 24px;
        }
    `;
    document.head.appendChild(style);
};

// Add styles when the file loads
addAgentProfileStyles();