// Agent Creator Page Component
const AgentCreator = ({ onBack, onCreateAgent }) => {
    const [agentName, setAgentName] = React.useState('');
    const [agentAvatar, setAgentAvatar] = React.useState('🤖');
    const [personality, setPersonality] = React.useState({
        openness: 0.5,
        conscientiousness: 0.5,
        extraversion: 0.5,
        agreeableness: 0.5,
        neuroticism: 0.5
    });
    const [isCreating, setIsCreating] = React.useState(false);
    const [creationStatus, setCreationStatus] = React.useState('');

    const avatars = ['🤖', '👾', '🦾', '👽', '🚀', '🌟', '⚡', '🔮', '🧠', '💻', '📱', '🎮'];

    const handlePersonalityChange = (trait, value) => {
        setPersonality(prev => ({
            ...prev,
            [trait]: parseFloat(value)
        }));
    };

    const handleCreateAgent = async () => {
        if (!agentName.trim()) {
            setCreationStatus('Пожалуйста, введите имя агента');
            return;
        }

        setIsCreating(true);
        setCreationStatus('Создание агента...');

        try {
            // Call the backend API to create the agent
            const response = await fetch('/api/agents', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: agentName,
                    avatar: agentAvatar,
                    personality: personality
                })
            });

            const result = await response.json();

            if (result.status === 'ok') {
                setCreationStatus('Агент успешно создан!');
                
                // Call the onCreateAgent callback if provided
                if (onCreateAgent) {
                    onCreateAgent(result.agent);
                }

                // Reset form after a delay
                setTimeout(() => {
                    setAgentName('');
                    setPersonality({
                        openness: 0.5,
                        conscientiousness: 0.5,
                        extraversion: 0.5,
                        agreeableness: 0.5,
                        neuroticism: 0.5
                    });
                    setCreationStatus('');
                }, 2000);
            } else {
                setCreationStatus('Ошибка при создании агента: ' + result.message);
            }
        } catch (error) {
            setCreationStatus('Ошибка при создании агента: ' + error.message);
        } finally {
            setIsCreating(false);
        }
    };

    const traitDescriptions = {
        openness: 'Открытость опыту',
        conscientiousness: 'Сознательность',
        extraversion: 'Экстраверсия',
        agreeableness: 'Доброжелательность',
        neuroticism: 'Нейротизм'
    };

    const traitTooltips = {
        openness: 'Насколько человек открыт новым идеям, опыту и приключениям',
        conscientiousness: 'Насколько человек организован, дисциплинирован и целеустремлён',
        extraversion: 'Насколько человек общителен, энергичен и уверен в себе',
        agreeableness: 'Насколько человек добр, доверчив и сотрудничает с другими',
        neuroticism: 'Насколько человек эмоционально нестабилен, тревожен и подвержен стрессу'
    };

    return React.createElement('div', { className: 'container' },
        // Back button
        React.createElement('div', { className: 'back-button-container' },
            React.createElement('button', {
                className: 'cyber-btn secondary',
                onClick: onBack
            }, '← Назад к дашборду')
        ),
        
        // Page header
        React.createElement('div', { className: 'page-header' },
            React.createElement('h1', null, 'Создание нового агента'),
            React.createElement('p', null, 'Настройте параметры вашего AI-агента')
        ),
        
        // Creation form
        React.createElement('div', { className: 'panel agent-creator-panel' },
            React.createElement('div', { className: 'panel-corner panel-corner-tl' }),
            React.createElement('div', { className: 'panel-corner panel-corner-tr' }),
            React.createElement('div', { className: 'panel-corner panel-corner-bl' }),
            React.createElement('div', { className: 'panel-corner panel-corner-br' }),
            
            React.createElement('div', { className: 'agent-creator-form' },
                // Basic info section
                React.createElement('div', { className: 'form-section' },
                    React.createElement('h3', null, 'Основная информация'),
                    
                    React.createElement('div', { className: 'form-group' },
                        React.createElement('label', { className: 'control-label' }, 'Имя агента'),
                        React.createElement('input', {
                            type: 'text',
                            className: 'cyber-input',
                            placeholder: 'Введите имя агента',
                            value: agentName,
                            onChange: (e) => setAgentName(e.target.value),
                            disabled: isCreating
                        })
                    ),
                    
                    React.createElement('div', { className: 'form-group' },
                        React.createElement('label', { className: 'control-label' }, 'Аватар'),
                        React.createElement('div', { className: 'avatar-selector' },
                            avatars.map(avatar => 
                                React.createElement('button', {
                                    key: avatar,
                                    className: `avatar-option ${agentAvatar === avatar ? 'selected' : ''}`,
                                    onClick: () => setAgentAvatar(avatar),
                                    disabled: isCreating
                                }, avatar)
                            )
                        )
                    )
                ),
                
                // Personality section
                React.createElement('div', { className: 'form-section' },
                    React.createElement('h3', null, 'Личность (модель OCEAN)'),
                    React.createElement('p', { className: 'section-description' }, 
                        'Настройте черты личности агента по пятифакторной модели'
                    ),
                    
                    Object.entries(personality).map(([trait, value]) => 
                        React.createElement('div', { key: trait, className: 'form-group' },
                            React.createElement('div', { className: 'trait-header' },
                                React.createElement('label', { className: 'control-label' }, traitDescriptions[trait]),
                                React.createElement('span', { className: 'trait-value' }, (value * 100).toFixed(0) + '%'),
                                React.createElement('div', { 
                                    className: 'tooltip-icon', 
                                    'data-tooltip': traitTooltips[trait] 
                                }, '?')
                            ),
                            React.createElement('input', {
                                type: 'range',
                                className: 'trait-slider',
                                min: '0',
                                max: '1',
                                step: '0.01',
                                value: value,
                                onChange: (e) => handlePersonalityChange(trait, e.target.value),
                                disabled: isCreating
                            })
                        )
                    )
                ),
                
                // Action buttons
                React.createElement('div', { className: 'form-actions' },
                    React.createElement('button', {
                        className: 'cyber-btn',
                        onClick: handleCreateAgent,
                        disabled: isCreating
                    }, isCreating ? 'Создание...' : 'Создать агента'),
                    
                    creationStatus && React.createElement('div', {
                        className: `creation-status ${creationStatus.includes('успешно') ? 'success' : 'error'}`
                    }, creationStatus)
                )
            )
        )
    );
};

// Add to global styles
const addAgentCreatorStyles = () => {
    const style = document.createElement('style');
    style.textContent = `
        .agent-creator-panel {
            max-width: 800px;
            margin: 0 auto;
        }
        
        .agent-creator-form {
            padding: 24px;
        }
        
        .form-section {
            margin-bottom: 32px;
        }
        
        .form-section h3 {
            margin-bottom: 16px;
            color: #00f0ff;
            font-size: 1.5rem;
        }
        
        .section-description {
            color: rgba(255, 255, 255, 0.7);
            margin-bottom: 24px;
            font-size: 0.9rem;
        }
        
        .form-group {
            margin-bottom: 24px;
        }
        
        .trait-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 8px;
        }
        
        .trait-header .control-label {
            flex: 1;
        }
        
        .trait-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            color: #00f0ff;
        }
        
        .tooltip-icon {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: rgba(0, 240, 255, 0.2);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
            cursor: help;
            position: relative;
        }
        
        .tooltip-icon:hover::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            width: 200px;
            white-space: normal;
            z-index: 100;
        }
        
        .trait-slider {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            outline: none;
            -webkit-appearance: none;
        }
        
        .trait-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #00f0ff;
            cursor: pointer;
            box-shadow: 0 0 10px rgba(0, 240, 255, 0.5);
        }
        
        .avatar-selector {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 12px;
        }
        
        .avatar-option {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(0, 240, 255, 0.2);
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .avatar-option:hover {
            background: rgba(0, 240, 255, 0.1);
            border-color: rgba(0, 240, 255, 0.4);
        }
        
        .avatar-option.selected {
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
            border-color: var(--neon-cyan);
            box-shadow: 0 0 15px rgba(0, 240, 255, 0.5);
        }
        
        .form-actions {
            display: flex;
            flex-direction: column;
            gap: 16px;
            margin-top: 32px;
        }
        
        .creation-status {
            padding: 16px;
            border-radius: 8px;
            text-align: center;
            font-weight: 600;
        }
        
        .creation-status.success {
            background: rgba(0, 255, 136, 0.1);
            border: 1px solid rgba(0, 255, 136, 0.3);
            color: #00ff88;
        }
        
        .creation-status.error {
            background: rgba(255, 0, 64, 0.1);
            border: 1px solid rgba(255, 0, 64, 0.3);
            color: #ff0040;
        }
        
        .page-header {
            text-align: center;
            margin-bottom: 32px;
        }
        
        .page-header h1 {
            font-size: 2.5rem;
            margin-bottom: 12px;
            color: #fff;
        }
        
        .page-header p {
            color: rgba(255, 255, 255, 0.7);
            font-size: 1.1rem;
        }
    `;
    document.head.appendChild(style);
};

// Add styles when the file loads
addAgentCreatorStyles();