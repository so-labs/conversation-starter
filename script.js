const generateButton = document.getElementById('generateButton');
const ideaDisplay = document.getElementById('ideaDisplay');
const modelSelect = document.getElementById('modelSelect');
const choiceOnly = document.getElementById('choiceOnly');

generateButton.addEventListener('click', async () => {
    ideaDisplay.textContent = 'お題を生成中...';
    generateButton.disabled = true;

    // 選択されたモデル名を取得
    const selectedModel = modelSelect.value;
    const mode = choiceOnly && choiceOnly.checked? 'choice_only' : 'default';

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ model: selectedModel, mode }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.idea) {
            if (data.choices && Array.isArray(data.choices) && data.choices.length >= 2) {
                ideaDisplay.innerHTML = `${data.idea}<br><br>` + data.choices.map((c, i) => `<button class="choice-btn">${i+1}. ${c}</button>`).join('');
            } else {
                ideaDisplay.textContent = data.idea;
            }
        } else {
            ideaDisplay.textContent = '生成に失敗しました。';
        }
    } catch (error) {
        console.error('クライアントサイドでのエラー:', error);
        ideaDisplay.textContent = '通信エラーが発生しました。';
    } finally {
        generateButton.disabled = false;
    }
});