// テーマ設定
const themeRadios = document.querySelectorAll('input[name="theme"]');
const prefersDarkScheme = window.matchMedia("(prefers-color-scheme: dark)");
const metaThemeColor = document.getElementById('theme-color-meta');

function updateThemeColor(isDark) {
    if (metaThemeColor) {
        metaThemeColor.setAttribute('content', isDark ? '#2C3E50' : '#F0F2F5');
    }
}

function applyTheme(theme) {
    let isDark = false;
    if (theme === 'system') {
        document.documentElement.removeAttribute('data-theme');
        isDark = prefersDarkScheme.matches;
    } else {
        document.documentElement.setAttribute('data-theme', theme);
        isDark = theme === 'dark';
    }
    updateThemeColor(isDark);
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

// カスタムセレクト要素
const customSelectWrapper = document.getElementById('customSelectWrapper');
const customSelectTrigger = document.getElementById('customSelectTrigger');
const customSelectValue = document.getElementById('customSelectValue');
const customSelectDropdown = document.getElementById('customSelectDropdown');

function openCustomSelect() {
    if (!customSelectWrapper) return;

    // 画面下端との距離をチェックし、狭ければ上向きに開く
    const rect = customSelectTrigger.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    if (spaceBelow < 250 && rect.top > spaceBelow) {
        customSelectWrapper.classList.add('open-upward');
    } else {
        customSelectWrapper.classList.remove('open-upward');
    }

    customSelectWrapper.classList.add('is-open');
    customSelectTrigger.setAttribute('aria-expanded', 'true');

    // 選択中アイテムを視認できる位置へスクロール
    const selectedOption = customSelectDropdown.querySelector('.custom-select-option.is-selected');
    if (selectedOption) {
        selectedOption.scrollIntoView({ block: 'nearest' });
    }
}

function closeCustomSelect() {
    if (!customSelectWrapper) return;
    customSelectWrapper.classList.remove('is-open');
    customSelectTrigger.setAttribute('aria-expanded', 'false');
}

function toggleCustomSelect() {
    if (customSelectWrapper.classList.contains('is-open')) {
        closeCustomSelect();
    } else {
        openCustomSelect();
    }
}

function selectCustomOption(val, text) {
    modelSelect.value = val;
    modelSelect.dispatchEvent(new Event('change'));
    if (customSelectValue) {
        customSelectValue.textContent = text;
    }
    const options = customSelectDropdown.querySelectorAll('.custom-select-option');
    options.forEach(opt => {
        const isSelected = opt.getAttribute('data-value') === val;
        opt.classList.toggle('is-selected', isSelected);
        opt.setAttribute('aria-selected', isSelected ? 'true' : 'false');
    });
    closeCustomSelect();
}

if (customSelectTrigger) {
    customSelectTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleCustomSelect();
    });

    customSelectTrigger.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            openCustomSelect();
        }
    });
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && customSelectWrapper && customSelectWrapper.classList.contains('is-open')) {
        closeCustomSelect();
        customSelectTrigger.focus();
    }
});

document.addEventListener('click', (e) => {
    if (customSelectWrapper && !customSelectWrapper.contains(e.target)) {
        closeCustomSelect();
    }
});

// モデル一覧の読み込みとセレクトボックス生成
async function loadModels() {
    try {
        const response = await fetch('./models.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const groups = await response.json();

        modelSelect.innerHTML = '';
        if (customSelectDropdown) customSelectDropdown.innerHTML = '';

        let hasSelected = false;
        let selectedName = '';

        groups.forEach((group) => {
            const optgroup = document.createElement('optgroup');
            optgroup.label = group.group;

            // カスタムドロップダウン用グループ
            const customGroup = document.createElement('div');
            customGroup.className = 'custom-select-group';
            const groupTitle = document.createElement('div');
            groupTitle.className = 'custom-select-group-title';
            groupTitle.textContent = group.group;
            customGroup.appendChild(groupTitle);

            group.models.forEach((model) => {
                // ネイティブoption（内部連携・フォールバック用）
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name;

                const isDefault = (model.default && !hasSelected);
                if (isDefault) {
                    option.selected = true;
                    hasSelected = true;
                    selectedName = model.name;
                }
                optgroup.appendChild(option);

                // カスタムoption
                const customOption = document.createElement('div');
                customOption.className = `custom-select-option${isDefault ? ' is-selected' : ''}`;
                customOption.setAttribute('role', 'option');
                customOption.setAttribute('data-value', model.id);
                customOption.setAttribute('aria-selected', isDefault ? 'true' : 'false');
                customOption.setAttribute('tabindex', '0');
                customOption.innerHTML = `
                    <span>${model.name}</span>
                    <svg class="custom-select-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                `;

                customOption.addEventListener('click', (e) => {
                    e.stopPropagation();
                    selectCustomOption(model.id, model.name);
                    customSelectTrigger.focus();
                });

                customOption.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        e.stopPropagation();
                        selectCustomOption(model.id, model.name);
                        customSelectTrigger.focus();
                    }
                });

                customGroup.appendChild(customOption);
            });

            modelSelect.appendChild(optgroup);
            if (customSelectDropdown) customSelectDropdown.appendChild(customGroup);
        });

        if (!hasSelected && modelSelect.options.length > 0) {
            modelSelect.options[0].selected = true;
            selectedName = modelSelect.options[0].textContent;
            const firstCustom = customSelectDropdown.querySelector('.custom-select-option');
            if (firstCustom) {
                firstCustom.classList.add('is-selected');
                firstCustom.setAttribute('aria-selected', 'true');
            }
        }

        if (customSelectValue && selectedName) {
            customSelectValue.textContent = selectedName;
        }
    } catch (error) {
        console.error('モデル一覧の取得に失敗しました:', error);
        modelSelect.innerHTML = '<option value="">モデルの取得に失敗しました</option>';
        if (customSelectValue) customSelectValue.textContent = 'モデルの取得に失敗しました';
        if (customSelectDropdown) {
            customSelectDropdown.innerHTML = '<div style="padding: 10px; color: var(--text-color); font-size: 0.9em; text-align: center;">モデルの取得に失敗しました</div>';
        }
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

// 設定パネルの開閉
const settingsToggle = document.getElementById('settingsToggle');
const settingsPanel = document.getElementById('settingsPanel');
const settingsClose = document.getElementById('settingsClose');

function openPanel() {
    settingsPanel.classList.add('is-open');
    settingsToggle.classList.add('is-open');
    settingsPanel.setAttribute('aria-hidden', 'false');
}

function closePanel() {
    closeCustomSelect();
    settingsPanel.classList.remove('is-open');
    settingsToggle.classList.remove('is-open');
    settingsPanel.setAttribute('aria-hidden', 'true');
}

if (settingsToggle && settingsPanel) {
    settingsToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        settingsPanel.classList.contains('is-open') ? closePanel() : openPanel();
    });

    if (settingsClose) {
        settingsClose.addEventListener('click', (e) => {
            e.stopPropagation();
            closePanel();
        });
    }

    // パネル外クリックで閉じる
    document.addEventListener('click', (e) => {
        if (!settingsPanel.contains(e.target) && e.target !== settingsToggle) {
            closePanel();
        }
    });
}

// スワイプで設定パネルの開閉
(function setupSwipeForSettings() {
    if (!settingsPanel || !settingsToggle) return;

    const THRESHOLD_X = 60;            // 横方向の最小移動量(px)
    const MIN_VELOCITY_X = 0.25;       // 横方向の最小速度(px/ms)
    const Y_RATIO_MAX = 0.6;           // |Δy| / |Δx| の上限。これを超えると縦成分優勢とみなして不発
    const MAX_DURATION = 1000;         // 長すぎるスワイプは意図的操作ではないとみなして不発

    let tracking = false;
    let startX = 0;
    let startY = 0;
    let startT = 0;

    document.addEventListener('touchstart', (e) => {
        if (e.touches.length !== 1) {
            tracking = false;
            return;
        }
        const touch = e.touches[0];
        tracking = true;
        startX = touch.clientX;
        startY = touch.clientY;
        startT = e.timeStamp;
    }, { passive: true });

    document.addEventListener('touchmove', (e) => {
        if (!tracking) return;
        // 縦スクロールを妨げないよう、ここでは何もしない(判定はtouchendで行う)
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
        if (!tracking) return;
        tracking = false;

        const changed = e.changedTouches[0];
        if (!changed) return;

        const dx = changed.clientX - startX; // 左スワイプは負、右スワイプは正
        const dy = changed.clientY - startY;
        const dt = e.timeStamp - startT;

        if (dt > MAX_DURATION) return;

        const absDx = Math.abs(dx);
        const absDy = Math.abs(dy);

        // 横移動量が閾値未満なら不発
        if (absDx < THRESHOLD_X) return;

        // 縦成分が横成分に対して大きすぎる場合は縦スクロールとみなして不発
        if (absDx > 0 && absDy / absDx > Y_RATIO_MAX) return;

        const velocity = absDx / Math.max(dt, 1);
        if (velocity < MIN_VELOCITY_X) return;

        const isOpen = settingsPanel.classList.contains('is-open');

        // パネルが閉じている → 左スワイプで開く
        if (!isOpen && dx < 0) {
            openPanel();
            return;
        }

        // パネルが開いている → 右スワイプで閉じる
        if (isOpen && dx > 0) {
            closePanel();
            return;
        }
    }, { passive: true });

    document.addEventListener('touchcancel', () => {
        tracking = false;
    }, { passive: true });
})();