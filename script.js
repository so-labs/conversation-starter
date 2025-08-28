const generateButton = document.getElementById('generateButton');
const ideaDisplay = document.getElementById('ideaDisplay');

generateButton.addEventListener('click', async () => {
    ideaDisplay.textContent = 'お題を生成中...';
    generateButton.disabled = true;

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
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