const generateButton = document.getElementById('generateButton');
const ideaDisplay = document.getElementById('ideaDisplay');
const modelSelect = document.getElementById('modelSelect');
const choiceOnly = document.getElementById('choiceOnly');
const customWordMode = document.getElementById('customWordMode');
const customWordInput = document.getElementById('customWordInput');

// ワード指定の有効/無効切り替え
if (customWordMode) {
    customWordMode.addEventListener('change', () => {
        customWordInput.disabled = !customWordMode.checked;
        if (customWordMode.checked) {
            customWordInput.focus();
        }
    });
}

generateButton.addEventListener('click', async () => {
    ideaDisplay.textContent = 'お題を生成中...';
    generateButton.disabled = true;

    // 選択されたモデル名を取得
    const selectedModel = modelSelect.value;
    let mode = choiceOnly && choiceOnly.checked ? 'choice_only' : 'default';
    let word = '';

    if (customWordMode && customWordMode.checked) {
        word = (customWordInput.value || '').trim().slice(0, 10);
        if (!word) {
            ideaDisplay.textContent = 'ワードを入力してください（単語・最大10文字）';
            generateButton.disabled = false;
            return;
        }
        mode = 'custom_word';
        if (choiceOnly && choiceOnly.checked) {
            mode = 'custom_word_choice';
        }
    }

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ model: selectedModel, mode, word }),
        });

        const data = await response.json();

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
            ideaDisplay.textContent = '生成に失敗しました。';
        }
    } catch (error) {
        console.error('クライアントサイドでのエラー:', error);
        ideaDisplay.textContent = error.message || '通信エラーが発生しました。';
    } finally {
        generateButton.disabled = false;
    }
});