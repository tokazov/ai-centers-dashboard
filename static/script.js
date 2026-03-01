// AI Centers Dashboard - Frontend Logic

let authToken = null;
let currentUser = null;

// === Auth ===

async function authenticateUser(telegramUser) {
    try {
        const response = await fetch('/api/auth/telegram', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(telegramUser)
        });

        if (!response.ok) {
            throw new Error('Authentication failed');
        }

        const data = await response.json();
        authToken = data.access_token;
        currentUser = data.user;

        // Сохраняем в localStorage
        localStorage.setItem('authToken', authToken);
        localStorage.setItem('currentUser', JSON.stringify(currentUser));

        showDashboard();
    } catch (error) {
        console.error('Auth error:', error);
        alert('Ошибка авторизации. Попробуйте снова.');
    }
}

function logout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    showAuthScreen();
}

function showAuthScreen() {
    document.getElementById('auth-screen').classList.remove('hidden');
    document.getElementById('dashboard-screen').classList.add('hidden');
}

function showDashboard() {
    document.getElementById('auth-screen').classList.add('hidden');
    document.getElementById('dashboard-screen').classList.remove('hidden');

    // Загружаем данные
    loadUserInfo();
    loadStats();
    loadConversations();
    loadConfig();
    loadSubscription();
}

// === API Helpers ===

async function apiRequest(endpoint, options = {}) {
    if (!authToken) {
        throw new Error('Not authenticated');
    }

    const headers = {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json',
        ...options.headers
    };

    const response = await fetch(endpoint, {
        ...options,
        headers
    });

    if (response.status === 401) {
        logout();
        throw new Error('Session expired');
    }

    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }

    return response.json();
}

// === Data Loading ===

function loadUserInfo() {
    if (currentUser) {
        document.getElementById('user-name').textContent = 
            `${currentUser.first_name} ${currentUser.last_name || ''}`.trim();
    }
}

async function loadStats() {
    try {
        const stats = await apiRequest('/api/stats');
        
        document.getElementById('stat-today').textContent = stats.today_messages;
        document.getElementById('stat-week').textContent = stats.week_messages;
        document.getElementById('stat-month').textContent = stats.month_messages;
        document.getElementById('stat-users').textContent = stats.unique_users;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadConversations() {
    try {
        const conversations = await apiRequest('/api/conversations?limit=20');
        
        const container = document.getElementById('conversations-list');
        
        if (conversations.length === 0) {
            container.innerHTML = '<p class="loading">Диалогов пока нет</p>';
            return;
        }

        container.innerHTML = conversations.map(conv => `
            <div class="conversation-item">
                <div class="conversation-header">
                    <span class="conversation-username">@${conv.username}</span>
                    <span>${new Date(conv.timestamp).toLocaleString('ru-RU')}</span>
                </div>
                <div class="conversation-message">
                    <strong>Вопрос:</strong>
                    <p>${escapeHtml(conv.message)}</p>
                </div>
                <div class="conversation-message">
                    <strong>Ответ бота:</strong>
                    <p>${escapeHtml(conv.response)}</p>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading conversations:', error);
        document.getElementById('conversations-list').innerHTML = 
            '<p class="loading">Ошибка загрузки диалогов</p>';
    }
}

async function loadConfig() {
    try {
        const config = await apiRequest('/api/config');
        
        document.getElementById('business_name').value = config.business_name || '';
        document.getElementById('schedule').value = config.schedule || '';
        document.getElementById('address').value = config.address || '';
        document.getElementById('phone').value = config.phone || '';
        
        // Загружаем услуги
        const servicesList = document.getElementById('services-list');
        servicesList.innerHTML = '';
        
        (config.services || []).forEach(service => {
            addService(service.name, service.price);
        });
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

async function loadSubscription() {
    try {
        const sub = await apiRequest('/api/subscription');
        
        const statusText = {
            'trial': '🆓 Пробный период',
            'active': '✅ Активна',
            'expired': '❌ Истекла'
        }[sub.status] || sub.status;
        
        document.getElementById('subscription-info').innerHTML = `
            <div class="subscription-status ${sub.status}">
                ${statusText}
            </div>
            ${sub.ends_at ? `<p>Действительна до: ${new Date(sub.ends_at).toLocaleDateString('ru-RU')}</p>` : ''}
        `;
    } catch (error) {
        console.error('Error loading subscription:', error);
        document.getElementById('subscription-info').innerHTML = 
            '<p class="loading">Ошибка загрузки информации о подписке</p>';
    }
}

// === Services Management ===

let serviceCounter = 0;

function addService(name = '', price = '') {
    const servicesList = document.getElementById('services-list');
    const id = `service-${serviceCounter++}`;
    
    const div = document.createElement('div');
    div.className = 'service-item';
    div.innerHTML = `
        <input type="text" placeholder="Название услуги" value="${escapeHtml(name)}" data-field="name">
        <input type="text" placeholder="Цена" value="${escapeHtml(price)}" data-field="price">
        <button type="button" onclick="removeService(this)">Удалить</button>
    `;
    
    servicesList.appendChild(div);
}

function removeService(button) {
    button.parentElement.remove();
}

// === Config Form ===

document.addEventListener('DOMContentLoaded', () => {
    // Проверяем авторизацию при загрузке
    const savedToken = localStorage.getItem('authToken');
    const savedUser = localStorage.getItem('currentUser');
    
    if (savedToken && savedUser) {
        authToken = savedToken;
        currentUser = JSON.parse(savedUser);
        showDashboard();
    } else {
        showAuthScreen();
    }

    // Обработчик формы конфигурации
    const configForm = document.getElementById('config-form');
    if (configForm) {
        configForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Собираем услуги
            const services = [];
            document.querySelectorAll('#services-list .service-item').forEach(item => {
                const name = item.querySelector('[data-field="name"]').value.trim();
                const price = item.querySelector('[data-field="price"]').value.trim();
                
                if (name && price) {
                    services.push({ name, price });
                }
            });
            
            const config = {
                business_name: document.getElementById('business_name').value,
                niche: 'other', // TODO: добавить выбор ниши
                services: services,
                schedule: document.getElementById('schedule').value,
                address: document.getElementById('address').value,
                phone: document.getElementById('phone').value,
                language: 'ru'
            };
            
            try {
                await apiRequest('/api/config', {
                    method: 'PUT',
                    body: JSON.stringify(config)
                });
                
                alert('✅ Настройки сохранены!');
            } catch (error) {
                console.error('Error saving config:', error);
                alert('❌ Ошибка при сохранении настроек');
            }
        });
    }
});

// === Utilities ===

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
