const generateButton = document.getElementById('generateButton');
const ideaDisplay = document.getElementById('ideaDisplay');
const modelSelect = document.getElementById('modelSelect');

generateButton.addEventListener('click', async () => {
    ideaDisplay.textContent = 'お題を生成中...';
    generateButton.disabled = true;

    // 選択されたモデル名を取得
    const selectedModel = modelSelect.value;

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ model: selectedModel }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.idea) {
            ideaDisplay.textContent = data.idea;
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