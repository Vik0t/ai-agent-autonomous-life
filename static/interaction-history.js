// Interaction History Component
const InteractionHistory = ({ agents, events }) => {
    // Filter events to show only message-related events
    const messageEvents = (events || []).filter(event => 
        event.text.includes('Сообщение') || 
        event.text.includes('сообщение') ||
        event.text.includes('чат') ||
        event.text.includes('Чат')
    ).slice(0, 20); // Show only last 20 messages

    // Get agent name by ID
    const getAgentName = (agentId) => {
        if (agentId === 'user') return 'Пользователь';
        const agent = agents.find(a => a.id === agentId);
        return agent ? agent.name : `Агент ${agentId}`;
    };

    // Parse message from event text
    const parseMessage = (text) => {
        // Try to extract sender and message content
        const messageMatch = text.match(/(?:от|к) ([^:]+): (.+)/i);
        if (messageMatch) {
            return {
                sender: messageMatch[1],
                content: messageMatch[2]
            };
        }
        return {
            sender: 'Система',
            content: text
        };
    };

    return React.createElement('div', { className: 'panel interaction-history-panel' },
        React.createElement('div', { className: 'panel-corner panel-corner-tl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-tr' }),
        React.createElement('div', { className: 'panel-corner panel-corner-bl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-br' }),
        
        React.createElement('h2', { className: 'panel-title' }, 'История Взаимодействий'),
        
        React.createElement('div', { className: 'interaction-history' },
            messageEvents.length > 0 ? 
                messageEvents.map((event, index) => {
                    const parsed = parseMessage(event.text);
                    return React.createElement('div', { 
                        key: event.id || index, 
                        className: 'interaction-item' 
                    },
                        React.createElement('div', { className: 'interaction-header' },
                            React.createElement('span', { className: 'interaction-sender' }, parsed.sender),
                            React.createElement('span', { className: 'interaction-time' }, event.timestamp)
                        ),
                        React.createElement('div', { className: 'interaction-content' }, parsed.content)
                    );
                }) :
                React.createElement('p', { className: 'empty-state' }, 'Нет записей о взаимодействиях')
        )
    );
};

// Add to global styles
const addInteractionHistoryStyles = () => {
    const style = document.createElement('style');
    style.textContent = `
        .interaction-history-panel {
            grid-column: span 6;
        }
        
        .interaction-history {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .interaction-item {
            padding: 15px;
            margin-bottom: 12px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            transition: all 0.3s ease;
        }
        
        .interaction-item:hover {
            border-color: rgba(0, 240, 255, 0.2);
            background: rgba(0, 0, 0, 0.4);
        }
        
        .interaction-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.85rem;
        }
        
        .interaction-sender {
            font-weight: 700;
            color: var(--neon-cyan);
        }
        
        .interaction-time {
            color: var(--neon-purple);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .interaction-content {
            font-size: 0.95rem;
            line-height: 1.5;
        }
        
        @media (max-width: 1200px) {
            .interaction-history-panel {
                grid-column: span 12;
            }
        }
    `;
    document.head.appendChild(style);
};

// Add styles when the file loads
addInteractionHistoryStyles();