// Цвета эмоций
const emotionColors = {
    happiness: '#00ff88',
    sadness: '#2196F3',
    anger: '#ff0040',
    fear: '#ffee00',
    surprise: '#ff00ff',
    disgust: '#9E9E9E'
};

// Иконки настроений
const moodIcons = {
    happy: '😊',
    sad: '😢',
    angry: '😠',
    scared: '😨',
    surprised: '😲',
    neutral: '😐'
};

// Переводы эмоций
const emotionTranslations = {
    happiness: 'Радость',
    sadness: 'Грусть',
    anger: 'Гнев',
    fear: 'Страх',
    surprise: 'Удивление',
    disgust: 'Отвращение'
};

// Генерация тестовых данных
const generateMockAgents = () => {
    const names = ['Алекса', 'Нексус', 'Кайрос', 'Зефир', 'Орион', 'Луна', 'Титан', 'Вега'];
    const personalities = [
        { openness: 0.8, conscientiousness: 0.6, extraversion: 0.9, agreeableness: 0.7, neuroticism: 0.3 },
        { openness: 0.4, conscientiousness: 0.9, extraversion: 0.3, agreeableness: 0.5, neuroticism: 0.6 },
        { openness: 0.9, conscientiousness: 0.4, extraversion: 0.7, agreeableness: 0.8, neuroticism: 0.2 },
        { openness: 0.6, conscientiousness: 0.7, extraversion: 0.5, agreeableness: 0.6, neuroticism: 0.4 },
        { openness: 0.7, conscientiousness: 0.5, extraversion: 0.8, agreeableness: 0.4, neuroticism: 0.5 },
        { openness: 0.5, conscientiousness: 0.8, extraversion: 0.4, agreeableness: 0.9, neuroticism: 0.3 },
        { openness: 0.8, conscientiousness: 0.3, extraversion: 0.6, agreeableness: 0.5, neuroticism: 0.7 },
        { openness: 0.3, conscientiousness: 0.9, extraversion: 0.2, agreeableness: 0.7, neuroticism: 0.4 }
    ];

    return names.map((name, i) => ({
        id: `agent-${i}`,
        name: name,
        avatar: ['🤖', '👾', '🦾', '👽', '🚀', '🌟', '⚡', '🔮'][i],
        personality: personalities[i],
        emotions: {
            happiness: Math.random(),
            sadness: Math.random() * 0.5,
            anger: Math.random() * 0.3,
            fear: Math.random() * 0.4,
            surprise: Math.random() * 0.6,
            disgust: Math.random() * 0.2
        },
        relationships: {},
        memory_count: Math.floor(Math.random() * 50) + 10,
        current_plan: ['Анализ данных', 'Общение с агентами', 'Изучение окружения', 'Планирование действий'][Math.floor(Math.random() * 4)],
        status: 'active',
        memories: [
            { time: '10:30', content: 'Встреча с Алексой, обсуждение проекта' },
            { time: '09:15', content: 'Получено сообщение от Нексуса' },
            { time: 'Вчера', content: 'Участие в групповой дискуссии' }
        ]
    }));
};

// Компонент заголовка
const Header = () => (
    React.createElement('header', { className: 'header' },
        React.createElement('h1', { className: 'glitch-text', 'data-text': 'КИБЕР РЫВОК' }, 'КИБЕР РЫВОК'),
        React.createElement('p', null, 'Симулятор автономных AI-агентов // Версия 2.0.77')
    )
);

// Компонент карточки агента
const AgentCard = ({ agent, isSelected, onClick }) => {
    const getDominantEmotion = () => {
        let max = 0;
        let dominant = 'neutral';
        Object.entries(agent.emotions).forEach(([emotion, value]) => {
            if (value > max) {
                max = value;
                dominant = emotion;
            }
        });
        return dominant;
    };

    const dominantEmotion = getDominantEmotion();
    const moodColor = emotionColors[dominantEmotion] || '#00f0ff';

    const emotionBars = Object.entries(agent.emotions)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 3)
        .map(([emotion, value]) => 
            React.createElement('div', { key: emotion, className: 'emotion-item' },
                React.createElement('span', { className: 'emotion-label' }, emotionTranslations[emotion]),
                React.createElement('div', { className: 'emotion-bar-bg' },
                    React.createElement('div', {
                        className: 'emotion-bar-fill',
                        style: {
                            width: `${value * 100}%`,
                            background: emotionColors[emotion]
                        }
                    })
                )
            )
        );

    return React.createElement('div', {
            className: `agent-card ${isSelected ? 'selected' : ''}`,
            onClick: () => onClick(agent)
        },
        React.createElement('div', {
            className: 'agent-avatar',
            style: {
                background: `linear-gradient(135deg, ${moodColor}, #b829dd)`,
                boxShadow: `0 0 20px ${moodColor}80`
            }
        }, agent.avatar),
        React.createElement('div', { className: 'agent-name' }, agent.name),
        React.createElement('div', { className: 'agent-status' },
            React.createElement('span', { className: 'status-dot' }),
            React.createElement('span', null, agent.current_plan)
        ),
        React.createElement('div', { className: 'emotion-bars' }, emotionBars)
    );
};

// Компонент панели управления
const ControlPanel = ({ agents, onAddEvent, onSendMessage, onSetSpeed, timeSpeed, setTimeSpeed }) => {
    const [newEvent, setNewEvent] = React.useState('');
    const [messageContent, setMessageContent] = React.useState('');
    const [recipient, setRecipient] = React.useState('');

    const handleAddEvent = () => {
        if (newEvent.trim()) {
            onAddEvent(newEvent);
            setNewEvent('');
        }
    };

    const handleSendMessage = () => {
        if (messageContent.trim() && recipient) {
            onSendMessage(recipient, messageContent);
            setMessageContent('');
            setRecipient('');
        }
    };

    const agentOptions = agents.map(agent => 
        React.createElement('option', { key: agent.id, value: agent.id }, agent.name)
    );

    return React.createElement('div', { className: 'panel control-panel' },
        React.createElement('div', { className: 'panel-corner panel-corner-tl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-tr' }),
        React.createElement('div', { className: 'panel-corner panel-corner-bl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-br' }),
        
        React.createElement('h2', { className: 'panel-title' }, 'Панель Управления'),
        
        React.createElement('div', { className: 'control-group' },
            React.createElement('label', { className: 'control-label' }, 'Глобальное Событие'),
            React.createElement('input', {
                type: 'text',
                className: 'cyber-input',
                placeholder: 'Например: Найден клад! Праздник! Буря...',
                value: newEvent,
                onChange: (e) => setNewEvent(e.target.value)
            }),
            React.createElement('button', {
                className: 'cyber-btn',
                onClick: handleAddEvent,
                style: { marginTop: '12px' }
            }, 'Добавить Событие')
        ),

        React.createElement('div', { className: 'control-group' },
            React.createElement('label', { className: 'control-label' }, 'Отправить Сообщение'),
            React.createElement('select', {
                className: 'cyber-select',
                value: recipient,
                onChange: (e) => setRecipient(e.target.value)
            },
                React.createElement('option', { value: '' }, 'Выберите агента'),
                agentOptions
            ),
            React.createElement('input', {
                type: 'text',
                className: 'cyber-input',
                placeholder: 'Сообщение...',
                value: messageContent,
                onChange: (e) => setMessageContent(e.target.value),
                style: { marginTop: '10px' }
            }),
            React.createElement('button', {
                className: 'cyber-btn secondary',
                onClick: handleSendMessage,
                style: { marginTop: '12px' }
            }, 'Отправить')
        ),

        React.createElement('div', { className: 'control-group' },
            React.createElement('label', { className: 'control-label' }, 'Скорость Времени'),
            React.createElement('div', { className: 'speed-control' },
                React.createElement('input', {
                    type: 'range',
                    className: 'speed-slider',
                    min: '0.1',
                    max: '5',
                    step: '0.1',
                    value: timeSpeed,
                    onChange: (e) => setTimeSpeed(parseFloat(e.target.value))
                }),
                React.createElement('span', { className: 'speed-value' }, `${timeSpeed.toFixed(1)}x`)
            ),
            React.createElement('button', {
                className: 'cyber-btn',
                onClick: onSetSpeed,
                style: { marginTop: '12px' }
            }, 'Применить')
        )
    );
};

// Компонент ленты событий
const EventFeed = ({ events }) => {
    const feedRef = React.useRef(null);

    React.useEffect(() => {
        if (feedRef.current) {
            feedRef.current.scrollTop = 0;
        }
    }, [events]);

    const getEventTypeClass = (text) => {
        if (text.includes('Сообщение')) return 'message';
        if (text.includes('Действие')) return 'action';
        if (text.includes('Эмоция')) return 'emotion';
        if (text.includes('Воспоминание')) return 'memory';
        return 'action';
    };

    const eventItems = events.map((event, index) => 
        React.createElement('div', { key: event.id || index, className: 'event-item' },
            React.createElement('div', { className: 'event-time' }, event.timestamp),
            React.createElement('span', { className: `event-type ${getEventTypeClass(event.text)}` },
                event.text.includes('Сообщение') ? 'MSG' : 
                event.text.includes('Эмоция') ? 'EMO' : 
                event.text.includes('Воспоминание') ? 'MEM' : 'ACT'
            ),
            event.text
        )
    );

    return React.createElement('div', { className: 'panel events-panel' },
        React.createElement('div', { className: 'panel-corner panel-corner-tl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-tr' }),
        React.createElement('div', { className: 'panel-corner panel-corner-bl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-br' }),
        
        React.createElement('h2', { className: 'panel-title' }, 'Лента Событий'),
        React.createElement('div', { className: 'event-feed', ref: feedRef }, eventItems)
    );
};

// Компонент графа отношений
const RelationshipGraph = ({ agents }) => {
    const svgRef = React.useRef(null);

    React.useEffect(() => {
        if (!svgRef.current || agents.length < 2) return;

        const width = svgRef.current.clientWidth;
        const height = 400;
        
        d3.select(svgRef.current).selectAll("*").remove();
        
        const svg = d3.select(svgRef.current)
            .attr("width", width)
            .attr("height", height);

        // Создаем связи на основе близости агентов
        const nodes = agents.map((agent, i) => ({
            id: agent.id,
            name: agent.name,
            avatar: agent.avatar,
            x: width/2 + Math.cos(i * 2 * Math.PI / agents.length) * 150,
            y: height/2 + Math.sin(i * 2 * Math.PI / agents.length) * 150
        }));

        const links = [];
        for (let i = 0; i < agents.length; i++) {
            for (let j = i + 1; j < agents.length; j++) {
                const affinity = (Math.random() - 0.5) * 2; // -1 to 1
                links.push({
                    source: agents[i].id,
                    target: agents[j].id,
                    affinity: affinity
                });
            }
        }

        const g = svg.append("g");

        // Связи
        const link = g.selectAll(".link")
            .data(links)
            .enter()
            .append("line")
            .attr("class", "link")
            .style("stroke", d => d.affinity > 0 ? "#00ff88" : "#ff0040")
            .style("stroke-width", d => Math.abs(d.affinity) * 3 + 1)
            .style("stroke-opacity", 0.6);

        // Узлы
        const node = g.selectAll(".node")
            .data(nodes)
            .enter()
            .append("g")
            .attr("class", "node")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

        // Круги узлов
        node.append("circle")
            .attr("r", 25)
            .style("fill", "url(#nodeGradient)")
            .style("stroke", "#00f0ff")
            .style("stroke-width", 2)
            .style("filter", "drop-shadow(0 0 10px #00f0ff)");

        // Градиент
        const defs = svg.append("defs");
        const gradient = defs.append("radialGradient")
            .attr("id", "nodeGradient");
        gradient.append("stop")
            .attr("offset", "0%")
            .style("stop-color", "#00f0ff");
        gradient.append("stop")
            .attr("offset", "100%")
            .style("stop-color", "#b829dd");

        // Аватары
        node.append("text")
            .attr("text-anchor", "middle")
            .attr("dy", "0.35em")
            .style("font-size", "20px")
            .text(d => d.avatar);

        // Подписи
        node.append("text")
            .attr("text-anchor", "middle")
            .attr("dy", "40")
            .style("fill", "#fff")
            .style("font-family", "JetBrains Mono")
            .style("font-size", "12px")
            .style("font-weight", "600")
            .text(d => d.name);

        // Симуляция
        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(40));

        simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node.attr("transform", d => `translate(${d.x},${d.y})`);
        });

        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }

        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }

        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }

    }, [agents]);

    return React.createElement('div', { className: 'panel graph-panel' },
        React.createElement('div', { className: 'panel-corner panel-corner-tl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-tr' }),
        React.createElement('div', { className: 'panel-corner panel-corner-bl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-br' }),
        
        React.createElement('h2', { className: 'panel-title' }, 'Граф Отношений'),
        React.createElement('svg', { ref: svgRef, id: 'relationship-graph' })
    );
};

// Компонент инспектора агента
const AgentInspector = ({ agent }) => {
    if (!agent) return React.createElement('div', { className: 'panel inspector-panel' },
        React.createElement('div', { className: 'panel-corner panel-corner-tl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-tr' }),
        React.createElement('div', { className: 'panel-corner panel-corner-bl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-br' }),
        React.createElement('h2', { className: 'panel-title' }, 'Инспектор Агента'),
        React.createElement('p', { className: 'empty-state' }, 'Выберите агента для просмотра детальной информации')
    );

    const traitTranslations = {
        openness: 'Открытость',
        conscientiousness: 'Сознательность',
        extraversion: 'Экстраверсия',
        agreeableness: 'Доброжелательность',
        neuroticism: 'Нейротизм'
    };

    const personalityTraits = Object.entries(agent.personality).map(([trait, value]) =>
        React.createElement('div', { key: trait, className: 'trait-row' },
            React.createElement('span', { className: 'trait-name' }, traitTranslations[trait]),
            React.createElement('div', { className: 'trait-bar' },
                React.createElement('div', { className: 'trait-bar-fill', style: { width: `${value * 100}%` } })
            ),
            React.createElement('span', { className: 'trait-value' }, `${(value * 100).toFixed(0)}%`)
        )
    );

    const emotionTraits = Object.entries(agent.emotions).map(([emotion, value]) =>
        React.createElement('div', { key: emotion, className: 'trait-row' },
            React.createElement('span', { className: 'trait-name' }, emotionTranslations[emotion]),
            React.createElement('div', { className: 'trait-bar' },
                React.createElement('div', {
                    className: 'trait-bar-fill',
                    style: {
                        width: `${value * 100}%`,
                        background: emotionColors[emotion]
                    }
                })
            ),
            React.createElement('span', {
                className: 'trait-value',
                style: { color: emotionColors[emotion] }
            }, `${(value * 100).toFixed(0)}%`)
        )
    );

    const memoryItems = agent.memories.map((memory, idx) =>
        React.createElement('div', { key: idx, className: 'memory-item' },
            React.createElement('div', { className: 'memory-time' }, memory.time),
            memory.content
        )
    );

    let relationshipItems;
    if (Object.entries(agent.relationships).length === 0) {
        relationshipItems = React.createElement('p', { className: 'empty-state' }, 'Нет установленных отношений');
    } else {
        relationshipItems = Object.entries(agent.relationships).map(([id, rel]) =>
            React.createElement('div', { key: id, className: 'relationship-item' },
                React.createElement('div', { className: 'rel-agent' },
                    React.createElement('div', { className: 'rel-avatar' }, '👤'),
                    React.createElement('div', { className: 'rel-info' },
                        React.createElement('div', { className: 'rel-name' }, `Агент ${id}`),
                        React.createElement('div', { className: 'rel-status' }, `Знакомство: ${(rel.familiarity * 100).toFixed(0)}%`)
                    )
                ),
                React.createElement('div', {
                    className: `rel-affinity ${rel.affinity > 0 ? 'positive' : rel.affinity < 0 ? 'negative' : 'neutral'}`
                }, `${rel.affinity > 0 ? '+' : ''}${rel.affinity.toFixed(2)}`)
            )
        );
    }

    const statItems = [
        React.createElement('div', { key: 'memory', className: 'trait-row' },
            React.createElement('span', { className: 'trait-name' }, 'Всего воспоминаний'),
            React.createElement('span', { className: 'trait-value' }, agent.memory_count)
        ),
        React.createElement('div', { key: 'messages', className: 'trait-row' },
            React.createElement('span', { className: 'trait-name' }, 'Сообщений отправлено'),
            React.createElement('span', { className: 'trait-value' }, Math.floor(Math.random() * 100))
        ),
        React.createElement('div', { key: 'activity', className: 'trait-row' },
            React.createElement('span', { className: 'trait-name' }, 'Время активности'),
            React.createElement('span', { className: 'trait-value' }, `${Math.floor(Math.random() * 24)}ч`)
        )
    ];

    return React.createElement('div', { className: 'panel inspector-panel' },
        React.createElement('div', { className: 'panel-corner panel-corner-tl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-tr' }),
        React.createElement('div', { className: 'panel-corner panel-corner-bl' }),
        React.createElement('div', { className: 'panel-corner panel-corner-br' }),
        
        React.createElement('h2', { className: 'panel-title' }, `Инспектор: ${agent.name}`),
        
        React.createElement('div', { className: 'inspector-grid' },
            React.createElement('div', { className: 'inspector-section' },
                React.createElement('h3', null, 'Личность (OCEAN)'),
                personalityTraits
            ),
            React.createElement('div', { className: 'inspector-section' },
                React.createElement('h3', null, 'Текущие Эмоции'),
                emotionTraits
            ),
            React.createElement('div', { className: 'inspector-section' },
                React.createElement('h3', null, 'Последние Воспоминания'),
                React.createElement('div', { className: 'memory-list' }, memoryItems)
            ),
            React.createElement('div', { className: 'inspector-section' },
                React.createElement('h3', null, 'Отношения'),
                React.createElement('div', { className: 'relationship-list' }, relationshipItems)
            ),
            React.createElement('div', { className: 'inspector-section' },
                React.createElement('h3', null, 'Текущий План'),
                React.createElement('p', {
                    style: {
                        fontSize: '1.1rem',
                        color: '#00f0ff',
                        fontWeight: 600,
                        marginBottom: '20px'
                    }
                }, agent.current_plan),
                React.createElement('h3', { style: { marginBottom: '10px' } }, 'Статус'),
                React.createElement('p', {
                    style: {
                        color: '#00ff88',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontWeight: 600
                    }
                },
                    React.createElement('span', {
                        style: {
                            width: '8px',
                            height: '8px',
                            background: '#00ff88',
                            borderRadius: '50%',
                            display: 'inline-block'
                        }
                    }),
                    'Активен'
                )
            ),
            React.createElement('div', { className: 'inspector-section' },
                React.createElement('h3', null, 'Статистика'),
                statItems
            )
        )
    );
};

// Главный компонент приложения
const App = () => {
    const [agents, setAgents] = React.useState([]);
    const [events, setEvents] = React.useState([]);
    const [selectedAgent, setSelectedAgent] = React.useState(null);
    const [timeSpeed, setTimeSpeed] = React.useState(1.0);
    const [isLoading, setIsLoading] = React.useState(true);

    // Инициализация
    React.useEffect(() => {
        // Имитация загрузки
        setTimeout(() => {
            const mockAgents = generateMockAgents();
            setAgents(mockAgents);
            
            // Добавляем начальные события
            const initialEvents = [
                { id: 1, text: 'Система инициализирована. 8 агентов активированы.', timestamp: new Date().toLocaleTimeString() },
                { id: 2, text: 'Алекса начала анализ окружения', timestamp: new Date().toLocaleTimeString() },
                { id: 3, text: 'Нексус отправил сообщение Кайросу', timestamp: new Date().toLocaleTimeString() }
            ];
            setEvents(initialEvents);
            
            document.getElementById('loading').classList.add('hidden');
            setIsLoading(false);
        }, 1500);

        // Симуляция входящих событий
        const interval = setInterval(() => {
            setEvents(prev => {
                const newEvent = {
                    id: Date.now(),
                    text: generateRandomEvent(),
                    timestamp: new Date().toLocaleTimeString()
                };
                return [newEvent, ...prev.slice(0, 49)];
            });
        }, 3000);

        return () => clearInterval(interval);
    }, []);

    const generateRandomEvent = () => {
        const events = [
            'Алекса изменила план действий',
            'Нексус вспомнил прошлое событие',
            'Кайрос получил сообщение от Зефира',
            'Орион обновил эмоциональное состояние',
            'Луна начала новую задачу',
            'Титан анализирует данные',
            'Вега отправила широковещательное сообщение',
            'Групповое обсуждение началось',
            'Обнаружена новая информация в окружении'
        ];
        return events[Math.floor(Math.random() * events.length)];
    };

    const handleAddEvent = (eventDesc) => {
        setEvents(prev => [{
            id: Date.now(),
            text: `Глобальное событие: ${eventDesc}`,
            timestamp: new Date().toLocaleTimeString()
        }, ...prev]);
    };

    const handleSendMessage = (recipient, content) => {
        const agent = agents.find(a => a.id === recipient);
        setEvents(prev => [{
            id: Date.now(),
            text: `Сообщение от Пользователя к ${agent?.name || recipient}: ${content}`,
            timestamp: new Date().toLocaleTimeString()
        }, ...prev]);
    };

    const handleSetSpeed = () => {
        setEvents(prev => [{
            id: Date.now(),
            text: `Скорость времени изменена на ${timeSpeed}x`,
            timestamp: new Date().toLocaleTimeString()
        }, ...prev]);
    };

    const agentCards = agents.map(agent =>
        React.createElement(AgentCard, {
            key: agent.id,
            agent: agent,
            isSelected: selectedAgent?.id === agent.id,
            onClick: setSelectedAgent
        })
    );

    const statItems = [
        React.createElement('div', { key: 'agents', className: 'stat-item' },
            React.createElement('div', { className: 'stat-value' }, agents.length),
            React.createElement('div', { className: 'stat-label' }, 'Активных Агентов')
        ),
        React.createElement('div', { key: 'events', className: 'stat-item' },
            React.createElement('div', { className: 'stat-value' }, events.length),
            React.createElement('div', { className: 'stat-label' }, 'Событий')
        ),
        React.createElement('div', { key: 'speed', className: 'stat-item' },
            React.createElement('div', { className: 'stat-value' }, `${timeSpeed.toFixed(1)}x`),
            React.createElement('div', { className: 'stat-label' }, 'Скорость Времени')
        ),
        React.createElement('div', { key: 'status', className: 'stat-item' },
            React.createElement('div', { className: 'stat-value', style: { color: '#00ff88' } }, 'ONLINE'),
            React.createElement('div', { className: 'stat-label' }, 'Статус Системы')
        )
    ];

    return React.createElement('div', { className: 'container' },
        React.createElement(Header),
        
        React.createElement('div', { className: 'stats-bar' }, statItems),

        React.createElement('div', { className: 'dashboard' },
            React.createElement('div', { className: 'panel agents-panel' },
                React.createElement('div', { className: 'panel-corner panel-corner-tl' }),
                React.createElement('div', { className: 'panel-corner panel-corner-tr' }),
                React.createElement('div', { className: 'panel-corner panel-corner-bl' }),
                React.createElement('div', { className: 'panel-corner panel-corner-br' }),
                
                React.createElement('h2', { className: 'panel-title' }, 'Активные Агенты'),
                React.createElement('div', { className: 'agent-grid' }, agentCards)
            ),

            React.createElement(ControlPanel, {
                agents: agents,
                onAddEvent: handleAddEvent,
                onSendMessage: handleSendMessage,
                onSetSpeed: handleSetSpeed,
                timeSpeed: timeSpeed,
                setTimeSpeed: setTimeSpeed
            })
        ),

        React.createElement('div', { className: 'dashboard' },
            React.createElement(EventFeed, { events: events }),
            React.createElement(RelationshipGraph, { agents: agents })
        ),

        React.createElement(AgentInspector, { agent: selectedAgent })
    );
};