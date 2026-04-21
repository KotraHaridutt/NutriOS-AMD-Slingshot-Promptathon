/**
 * NutriOS — Frontend Application Logic
 * 
 * Single-page app with:
 * - JWT token management (localStorage)
 * - All API endpoint integrations
 * - Tab-based navigation
 * - Chat state management
 * - File upload handling
 */

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

const state = {
    token: localStorage.getItem('nutrios_token') || null,
    userName: localStorage.getItem('nutrios_user_name') || '',
    userId: localStorage.getItem('nutrios_user_id') || '',
    chatHistory: [],
    currentTab: 'dashboard',
    selectedPhoto: null,
};

// API base URL — auto-detects Codespace forwarded URL vs localhost
const API_BASE = window.location.origin;

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    // Check if already authenticated
    if (state.token) {
        showApp();
    } else {
        showAuth();
    }

    // Setup drag-and-drop for photo upload
    setupDragDrop();

    // Auto-resize chat textarea
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
        });
    }
});

// ═══════════════════════════════════════════════════════════════
// AUTH
// ═══════════════════════════════════════════════════════════════

async function handleLogin() {
    const name = document.getElementById('auth-name').value.trim() || 'Demo User';
    const userId = document.getElementById('auth-userid').value.trim() || 'demo_user_001';
    const btn = document.getElementById('auth-btn');

    setButtonLoading(btn, true);

    try {
        const res = await fetch(`${API_BASE}/auth/demo-token?user_id=${encodeURIComponent(userId)}&name=${encodeURIComponent(name)}`, {
            method: 'POST',
        });

        if (!res.ok) throw new Error(`Auth failed: ${res.status}`);

        const data = await res.json();
        state.token = data.access_token;
        state.userName = name;
        state.userId = userId;

        localStorage.setItem('nutrios_token', state.token);
        localStorage.setItem('nutrios_user_name', state.userName);
        localStorage.setItem('nutrios_user_id', state.userId);

        showApp();
        showToast('Welcome to NutriOS! 🍎', 'success');
    } catch (err) {
        console.error('Login error:', err);
        showToast('Failed to authenticate. Is the server running?', 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

function handleLogout() {
    state.token = null;
    state.userName = '';
    state.userId = '';
    state.chatHistory = [];
    localStorage.removeItem('nutrios_token');
    localStorage.removeItem('nutrios_user_name');
    localStorage.removeItem('nutrios_user_id');
    showAuth();
    showToast('Logged out successfully', 'info');
}

function showAuth() {
    document.getElementById('auth-screen').classList.add('active');
    document.getElementById('app-screen').classList.remove('active');
}

function showApp() {
    document.getElementById('auth-screen').classList.remove('active');
    document.getElementById('app-screen').classList.add('active');

    // Update UI with user info
    const initial = state.userName.charAt(0).toUpperCase();
    document.getElementById('user-avatar').textContent = initial;
    document.getElementById('user-name-display').textContent = state.userName.split(' ')[0];
    document.getElementById('greeting-name').textContent = state.userName.split(' ')[0];
    document.getElementById('token-display').textContent = state.token || '—';

    // Set greeting based on time
    const hour = new Date().getHours();
    let greeting = 'morning';
    if (hour >= 12 && hour < 17) greeting = 'afternoon';
    else if (hour >= 17) greeting = 'evening';
    document.getElementById('greeting-time').textContent = greeting;

    // Load profile data
    loadProfile();
    // Try to load report stats
    loadDashboardStats();
}

// ═══════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════

function switchTab(tabName) {
    state.currentTab = tabName;

    // Update nav tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabName}`);
    });
}

// ═══════════════════════════════════════════════════════════════
// API HELPER
// ═══════════════════════════════════════════════════════════════

async function apiCall(endpoint, options = {}) {
    const headers = {
        'Authorization': `Bearer ${state.token}`,
        ...options.headers,
    };

    // Don't set Content-Type for FormData (browser sets it with boundary)
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    const res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
    });

    if (res.status === 401) {
        showToast('Session expired. Please log in again.', 'error');
        handleLogout();
        throw new Error('Unauthorized');
    }

    return res;
}

// ═══════════════════════════════════════════════════════════════
// DASHBOARD — NUDGE
// ═══════════════════════════════════════════════════════════════

async function getNudge() {
    const btn = document.getElementById('nudge-btn');
    const lat = parseFloat(document.getElementById('lat-input').value) || 37.7749;
    const lng = parseFloat(document.getElementById('lng-input').value) || -122.4194;

    setButtonLoading(btn, true);
    document.getElementById('nudge-content').innerHTML = '<p class="text-muted">Generating your personalized nudge...</p>';

    try {
        const res = await apiCall('/nudge', {
            method: 'POST',
            body: JSON.stringify({
                latitude: lat,
                longitude: lng,
                activity_level: 'moderate',
            }),
        });

        if (!res.ok) throw new Error(`Nudge failed: ${res.status}`);

        const data = await res.json();

        // Render nudge text
        document.getElementById('nudge-content').innerHTML = `
            <p class="nudge-text">${escapeHtml(data.nudge)}</p>
        `;

        // Render nearby places
        const placesEl = document.getElementById('nudge-places');
        if (data.nearby_places && data.nearby_places.length > 0) {
            placesEl.innerHTML = data.nearby_places.map(p => `
                <div class="place-chip">
                    📍 ${escapeHtml(p.name)}
                    ${p.rating ? `<span class="rating">★${p.rating}</span>` : ''}
                    ${p.distance_meters ? `<span>~${Math.round(p.distance_meters)}m</span>` : ''}
                </div>
            `).join('');
            placesEl.hidden = false;
        } else {
            placesEl.hidden = true;
        }

        // Render next event
        const eventEl = document.getElementById('nudge-event');
        if (data.next_event) {
            eventEl.innerHTML = `📅 Next: <strong>${escapeHtml(data.next_event.summary)}</strong>
                ${data.next_event.minutes_until ? ` in ${data.next_event.minutes_until} min` : ''}`;
            eventEl.hidden = false;
        } else {
            eventEl.hidden = true;
        }

        showToast('Nudge generated! 🎯', 'success');
    } catch (err) {
        console.error('Nudge error:', err);
        document.getElementById('nudge-content').innerHTML = `
            <p class="nudge-placeholder">Could not generate nudge. Please try again.</p>
        `;
        showToast('Failed to get nudge', 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

function getGeolocation() {
    if (!navigator.geolocation) {
        showToast('Geolocation not supported by your browser', 'error');
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (pos) => {
            document.getElementById('lat-input').value = pos.coords.latitude.toFixed(4);
            document.getElementById('lng-input').value = pos.coords.longitude.toFixed(4);
            showToast('Location updated! 📍', 'success');
        },
        (err) => {
            showToast('Could not get location: ' + err.message, 'error');
        }
    );
}

async function loadDashboardStats() {
    try {
        const res = await apiCall('/report/weekly');
        if (res.ok) {
            const data = await res.json();
            const today = new Date().toISOString().slice(0, 10);
            const todayData = data.daily_breakdown?.find(d => d.date === today);

            document.getElementById('stat-meals').textContent = todayData?.meal_count ?? '0';
            document.getElementById('stat-calories').textContent = todayData ? `${Math.round(todayData.total_calories)}` : '0';
            document.getElementById('stat-streak').textContent = `${data.habit_score?.streak_days ?? 0}🔥`;
            document.getElementById('stat-score').textContent = Math.round(data.habit_score?.overall_score ?? 0);
        }
    } catch (err) {
        // Stats are non-critical, silently fail
        console.log('Stats load deferred:', err.message);
    }
}

// ═══════════════════════════════════════════════════════════════
// MEAL LOGGING
// ═══════════════════════════════════════════════════════════════

function switchLogMode(mode) {
    document.querySelectorAll('.sub-tab').forEach((tab, i) => {
        tab.classList.toggle('active', (mode === 'photo' && i === 0) || (mode === 'manual' && i === 1));
    });
    document.getElementById('log-photo').classList.toggle('active', mode === 'photo');
    document.getElementById('log-manual').classList.toggle('active', mode === 'manual');
    document.getElementById('log-result').hidden = true;
}

function setupDragDrop() {
    const zone = document.getElementById('upload-zone');
    if (!zone) return;

    ['dragenter', 'dragover'].forEach(evt => {
        zone.addEventListener(evt, (e) => {
            e.preventDefault();
            zone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(evt => {
        zone.addEventListener(evt, (e) => {
            e.preventDefault();
            zone.classList.remove('drag-over');
        });
    });

    zone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });
}

function handlePhotoSelect(event) {
    const file = event.target.files[0];
    if (file) handleFile(file);
}

function handleFile(file) {
    if (!file.type.match(/^image\/(jpeg|png|webp)$/)) {
        showToast('Please upload a JPEG, PNG, or WebP image', 'error');
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        showToast('Image too large. Maximum 10MB', 'error');
        return;
    }

    state.selectedPhoto = file;

    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('preview-img').src = e.target.result;
        document.getElementById('photo-preview').hidden = false;
        document.getElementById('upload-zone').style.display = 'none';
        document.getElementById('photo-submit-btn').disabled = false;
    };
    reader.readAsDataURL(file);
}

function clearPhoto() {
    state.selectedPhoto = null;
    document.getElementById('photo-preview').hidden = true;
    document.getElementById('upload-zone').style.display = '';
    document.getElementById('photo-submit-btn').disabled = true;
    document.getElementById('photo-input').value = '';
}

async function submitPhoto() {
    if (!state.selectedPhoto) return;

    const btn = document.getElementById('photo-submit-btn');
    setButtonLoading(btn, true);

    try {
        const formData = new FormData();
        formData.append('photo', state.selectedPhoto);

        const res = await apiCall('/log/photo', {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `Upload failed: ${res.status}`);
        }

        const data = await res.json();
        showLogResult(data.meal, data.message);
        clearPhoto();
        showToast(data.message, 'success');
    } catch (err) {
        console.error('Photo upload error:', err);
        showToast(err.message || 'Failed to analyze photo', 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

async function submitManual() {
    const desc = document.getElementById('food-desc').value.trim();
    const mealType = document.getElementById('meal-type').value;

    if (!desc) {
        showToast('Please describe what you ate', 'error');
        return;
    }

    const btn = document.getElementById('manual-submit-btn');
    setButtonLoading(btn, true);

    try {
        const res = await apiCall('/log/manual', {
            method: 'POST',
            body: JSON.stringify({
                food_description: desc,
                meal_type: mealType,
            }),
        });

        if (!res.ok) throw new Error(`Manual log failed: ${res.status}`);

        const data = await res.json();
        showLogResult(data.meal, data.message);
        document.getElementById('food-desc').value = '';
        showToast(data.message, 'success');
    } catch (err) {
        console.error('Manual log error:', err);
        showToast('Failed to log meal', 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

function showLogResult(meal, message) {
    const el = document.getElementById('log-result');
    const content = document.getElementById('log-result-content');

    const macros = meal.macros || {};
    const confidence = meal.confidence ? `${Math.round(meal.confidence * 100)}%` : '—';

    content.innerHTML = `
        <p><strong>${escapeHtml(meal.food_name)}</strong></p>
        ${meal.description ? `<p class="text-muted">${escapeHtml(meal.description)}</p>` : ''}
        <div class="macro-grid">
            <div class="macro-item">
                <div class="macro-value">${Math.round(macros.calories || 0)}</div>
                <div class="macro-label">Calories</div>
            </div>
            <div class="macro-item">
                <div class="macro-value">${Math.round(macros.protein_g || 0)}g</div>
                <div class="macro-label">Protein</div>
            </div>
            <div class="macro-item">
                <div class="macro-value">${Math.round(macros.carbs_g || 0)}g</div>
                <div class="macro-label">Carbs</div>
            </div>
            <div class="macro-item">
                <div class="macro-value">${Math.round(macros.fat_g || 0)}g</div>
                <div class="macro-label">Fat</div>
            </div>
            <div class="macro-item">
                <div class="macro-value">${confidence}</div>
                <div class="macro-label">Confidence</div>
            </div>
        </div>
    `;

    el.hidden = false;
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ═══════════════════════════════════════════════════════════════
// CHAT COACH
// ═══════════════════════════════════════════════════════════════

function handleChatKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
    }
}

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    const btn = document.getElementById('chat-send-btn');
    setButtonLoading(btn, true);
    input.value = '';
    input.style.height = 'auto';

    // Add user message to UI
    addChatMessage('user', message);

    try {
        const res = await apiCall('/coach', {
            method: 'POST',
            body: JSON.stringify({
                message: message,
                conversation_history: state.chatHistory.slice(-10),
            }),
        });

        if (!res.ok) throw new Error(`Coach failed: ${res.status}`);

        const data = await res.json();
        addChatMessage('assistant', data.reply);

        // Update conversation history
        state.chatHistory.push(
            { role: 'user', content: message },
            { role: 'assistant', content: data.reply }
        );
    } catch (err) {
        console.error('Coach error:', err);
        addChatMessage('assistant', "I'm having a brief hiccup. Could you try asking again?");
        showToast('Coach response failed', 'error');
    } finally {
        setButtonLoading(btn, false);
        input.focus();
    }
}

function addChatMessage(role, content) {
    const container = document.getElementById('chat-messages');
    const avatar = role === 'user'
        ? state.userName.charAt(0).toUpperCase()
        : '🤖';

    const msgEl = document.createElement('div');
    msgEl.className = `chat-message ${role}`;
    msgEl.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-bubble">
            <p>${formatChatContent(content)}</p>
        </div>
    `;

    container.appendChild(msgEl);
    container.scrollTop = container.scrollHeight;
}

function formatChatContent(text) {
    // Basic markdown-like formatting
    return escapeHtml(text)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
}

// ═══════════════════════════════════════════════════════════════
// WEEKLY REPORT
// ═══════════════════════════════════════════════════════════════

async function getReport(format) {
    const jsonBtn = document.getElementById('report-json-btn');
    const htmlBtn = document.getElementById('report-html-btn');

    if (format === 'html') {
        // Open HTML report in iframe
        try {
            const res = await apiCall(`/report/weekly?format=html`);
            if (!res.ok) throw new Error(`Report failed: ${res.status}`);

            const html = await res.text();
            const iframe = document.getElementById('report-iframe');
            iframe.srcdoc = html;

            document.getElementById('report-content').hidden = true;
            document.getElementById('report-html-container').hidden = false;
            showToast('HTML report loaded!', 'success');
        } catch (err) {
            console.error('HTML report error:', err);
            showToast('Failed to load HTML report', 'error');
        }
        return;
    }

    // JSON report
    setButtonLoading(jsonBtn, true);

    try {
        const res = await apiCall('/report/weekly');
        if (!res.ok) throw new Error(`Report failed: ${res.status}`);

        const data = await res.json();
        renderJsonReport(data);

        document.getElementById('report-content').hidden = false;
        document.getElementById('report-html-container').hidden = true;
        showToast('Report loaded! 📊', 'success');
    } catch (err) {
        console.error('Report error:', err);
        showToast('Failed to load report', 'error');
    } finally {
        setButtonLoading(jsonBtn, false);
    }
}

function renderJsonReport(data) {
    const hs = data.habit_score || {};

    // Scores
    document.getElementById('report-scores').innerHTML = `
        <div class="score-card">
            <div class="score-value">${Math.round(hs.overall_score || 0)}</div>
            <div class="score-label">Overall Score</div>
        </div>
        <div class="score-card">
            <div class="score-value">${Math.round(hs.consistency_score || 0)}</div>
            <div class="score-label">Consistency</div>
        </div>
        <div class="score-card">
            <div class="score-value">${Math.round(hs.variety_score || 0)}</div>
            <div class="score-label">Variety</div>
        </div>
        <div class="score-card">
            <div class="score-value">${Math.round(hs.timing_score || 0)}</div>
            <div class="score-label">Timing</div>
        </div>
        <div class="score-card">
            <div class="score-value">${hs.streak_days || 0}🔥</div>
            <div class="score-label">Streak</div>
        </div>
    `;

    // Daily breakdown table
    const days = data.daily_breakdown || [];
    const rows = days.map(d => {
        const barWidth = Math.min(d.total_calories / 25, 100);
        return `
            <tr>
                <td>${d.date}</td>
                <td>${d.meal_count}</td>
                <td><div class="cal-bar" style="width:${barWidth}%">${Math.round(d.total_calories)}</div></td>
                <td>${Math.round(d.total_protein_g)}g</td>
                <td>${Math.round(d.total_carbs_g)}g</td>
                <td>${Math.round(d.total_fat_g)}g</td>
            </tr>
        `;
    }).join('');

    document.getElementById('report-daily').innerHTML = `
        <h3>📅 Daily Breakdown</h3>
        <p class="text-muted">Average: ${Math.round(data.average_daily_calories || 0)} kcal/day</p>
        <table class="report-table">
            <thead>
                <tr><th>Date</th><th>Meals</th><th>Calories</th><th>Protein</th><th>Carbs</th><th>Fat</th></tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;

    // Insights
    const insights = data.insights || [];
    document.getElementById('report-insights').innerHTML = `
        <h3>💡 AI Insights</h3>
        ${insights.map(i => `<div class="insight-item">${escapeHtml(i)}</div>`).join('')}
    `;
}

// ═══════════════════════════════════════════════════════════════
// PROFILE
// ═══════════════════════════════════════════════════════════════

async function loadProfile() {
    try {
        const res = await apiCall('/profile');
        if (res.ok) {
            const profile = await res.json();
            document.getElementById('profile-name').value = profile.name || '';
            document.getElementById('profile-goal').value = profile.goal || 'eat_healthier';
            document.getElementById('profile-calories').value = profile.daily_calorie_target || 2000;
            document.getElementById('profile-restrictions').value = (profile.dietary_restrictions || []).join(', ');
        }
    } catch (err) {
        console.log('Profile load deferred:', err.message);
    }
}

async function saveProfile() {
    const btn = document.getElementById('profile-save-btn');
    const statusEl = document.getElementById('profile-status');
    setButtonLoading(btn, true);

    try {
        const restrictions = document.getElementById('profile-restrictions').value
            .split(',')
            .map(s => s.trim())
            .filter(Boolean);

        const res = await apiCall('/profile', {
            method: 'PUT',
            body: JSON.stringify({
                name: document.getElementById('profile-name').value.trim(),
                goal: document.getElementById('profile-goal').value,
                daily_calorie_target: parseInt(document.getElementById('profile-calories').value) || 2000,
                dietary_restrictions: restrictions,
            }),
        });

        if (!res.ok) throw new Error(`Profile update failed: ${res.status}`);

        statusEl.textContent = '✅ Profile saved successfully!';
        statusEl.className = 'status-message status-success';
        statusEl.hidden = false;
        showToast('Profile updated! 💾', 'success');

        // Update user name in nav
        const newName = document.getElementById('profile-name').value.trim();
        if (newName) {
            state.userName = newName;
            localStorage.setItem('nutrios_user_name', newName);
            document.getElementById('user-avatar').textContent = newName.charAt(0).toUpperCase();
            document.getElementById('user-name-display').textContent = newName.split(' ')[0];
            document.getElementById('greeting-name').textContent = newName.split(' ')[0];
        }
    } catch (err) {
        console.error('Profile save error:', err);
        statusEl.textContent = '❌ Failed to save profile';
        statusEl.className = 'status-message status-error';
        statusEl.hidden = false;
        showToast('Failed to save profile', 'error');
    } finally {
        setButtonLoading(btn, false);
        setTimeout(() => { statusEl.hidden = true; }, 3000);
    }
}

function copyToken() {
    const token = state.token;
    if (token) {
        navigator.clipboard.writeText(token).then(() => {
            showToast('Token copied to clipboard! 📋', 'success');
        }).catch(() => {
            // Fallback for non-HTTPS
            const el = document.getElementById('token-display');
            const range = document.createRange();
            range.selectNodeContents(el);
            window.getSelection().removeAllRanges();
            window.getSelection().addRange(range);
            showToast('Select and copy the token manually', 'info');
        });
    }
}

// ═══════════════════════════════════════════════════════════════
// UI UTILITIES
// ═══════════════════════════════════════════════════════════════

function setButtonLoading(btn, loading) {
    if (!btn) return;
    const text = btn.querySelector('.btn-text');
    const loader = btn.querySelector('.btn-loader');

    if (loading) {
        btn.disabled = true;
        if (text) text.hidden = true;
        if (loader) loader.hidden = false;
    } else {
        btn.disabled = false;
        if (text) text.hidden = false;
        if (loader) loader.hidden = true;
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 4000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
