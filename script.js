// テーマ設定
const themeRadios = document.querySelectorAll('input[name="theme"]');
const prefersDarkScheme = window.matchMedia("(prefers-color-scheme: dark)");

function applyTheme(theme) {
    if (theme === 'system') {
        document.documentElement.removeAttribute('data-theme');
    } else {
        document.documentElement.setAttribute('data-theme', theme);
    }
}

const savedTheme = localStorage.getItem('theme') || 'system';
const selectedRadio = document.querySelector(`input[name="theme"][value="${savedTheme}"]`);
if (selectedRadio) {
    selectedRadio.checked = true;
}
applyTheme(savedTheme);

themeRadios.forEach(radio => {
    radio.addEventListener('change', (e) => {
        const theme = e.target.value;
        localStorage.setItem('theme', theme);
        applyTheme(theme);
    });
});

prefersDarkScheme.addEventListener('change', () => {
    const currentTheme = localStorage.getItem('theme') || 'system';
    if (currentTheme === 'system') {
        applyTheme('system');
    }
});

const generateButton = document.getElementById('generateButton');
const ideaDisplay = document.getElementById('ideaDisplay');
const errorDisplay = document.getElementById('errorDisplay');
const modelSelect = document.getElementById('modelSelect');
const choiceOnly = document.getElementById('choiceOnly');
const customWordMode = document.getElementById('customWordMode');
const customWordInput = document.getElementById('customWordInput');
const loadingModal = document.getElementById('loadingModal');

// ワード指定の有効/無効切り替え
if (customWordMode) {
    customWordMode.addEventListener('change', () => {
        customWordInput.disabled = !customWordMode.checked;
        if (customWordMode.checked) {
            customWordInput.focus();
        }
    });
}

// モデル一覧の読み込みとセレクトボックス生成
async function loadModels() {
    try {
        const response = await fetch('./models.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const groups = await response.json();

        modelSelect.innerHTML = '';
        let hasSelected = false;

        groups.forEach((group) => {
            const optgroup = document.createElement('optgroup');
            optgroup.label = group.group;

            group.models.forEach((model) => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name;
                if (model.default && !hasSelected) {
                    option.selected = true;
                    hasSelected = true;
                }
                optgroup.appendChild(option);
            });

            modelSelect.appendChild(optgroup);
        });

        if (!hasSelected && modelSelect.options.length > 0) {
            modelSelect.options[0].selected = true;
        }
    } catch (error) {
        console.error('モデル一覧の取得に失敗しました:', error);
        modelSelect.innerHTML = '<option value="">モデルの取得に失敗しました</option>';
    }
}

loadModels();

generateButton.addEventListener('click', async () => {
    errorDisplay.textContent = '';
    generateButton.disabled = true;

    // 選択されたモデル名を取得
    const selectedModel = modelSelect.value;
    if (!selectedModel) {
        errorDisplay.textContent = 'モデルを選択してください。';
        generateButton.disabled = false;
        return;
    }
    let mode = choiceOnly && choiceOnly.checked ? 'choice_only' : 'default';
    let word = '';

    if (customWordMode && customWordMode.checked) {
        word = (customWordInput.value || '').trim().slice(0, 10);
        if (!word) {
            errorDisplay.textContent = 'ワードを入力してください（単語・最大10文字）';
            generateButton.disabled = false;
            return;
        }
        mode = 'custom_word';
        if (choiceOnly && choiceOnly.checked) {
            mode = 'custom_word_choice';
        }
    }

    loadingModal.classList.remove('hidden');

    const abortController = new AbortController();
    const timeoutId = setTimeout(() => {
        abortController.abort();
    }, 20000); // 20秒タイムアウト

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ model: selectedModel, mode, word }),
            signal: abortController.signal,
        });

        clearTimeout(timeoutId);

        let data = {};
        try {
            data = await response.json();
        } catch {
            if (!response.ok) {
                throw new Error(`通信エラーが発生しました (HTTP ${response.status})`);
            }
        }

        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        if (data.idea) {
            if (data.choices && Array.isArray(data.choices) && data.choices.length >= 2) {
                ideaDisplay.innerHTML = `${data.idea}<br><br>` + data.choices.map((c, i) => `<button class="choice-btn">${i + 1}. ${c}</button>`).join('');
            } else {
                ideaDisplay.textContent = data.idea;
            }
        } else {
            ideaDisplay.textContent = '';
            errorDisplay.textContent = '生成に失敗しました。';
        }
    } catch (error) {
        clearTimeout(timeoutId);
        console.error('クライアントサイドでのエラー:', error);
        ideaDisplay.textContent = '';
        if (error.name === 'AbortError' || error.name === 'TimeoutError') {
            errorDisplay.textContent = '生成処理がタイムアウトしました（20秒）。混雑している可能性があるため、再度試すか別のモデルをお試しください。';
        } else {
            errorDisplay.textContent = error.message || '通信エラーが発生しました。';
        }
    } finally {
        generateButton.disabled = false;
        loadingModal.classList.add('hidden');
    }
});

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('./sw.js').catch((error) => {
            console.error('Service Worker registration failed:', error);
        });
    });
}