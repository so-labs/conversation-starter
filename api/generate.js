import { GoogleGenAI } from "@google/genai";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

// ESモジュールの環境で__dirnameと__filenameを再現
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ファイルを読み込み、BOMを削除する関数
const readJsonFile = (filePath) => {
    const fileContent = fs.readFileSync(filePath, "utf8");
    return JSON.parse(fileContent.replace(/^\uFEFF/, ""));
};

const questionsData = readJsonFile(path.join(__dirname, "questions.json"));
const promptsData = readJsonFile(path.join(__dirname, "prompts.json"));
// 汎用NGリスト（naughty-words）を起動時に一度だけ読み込み
const ngWords = readJsonFile(path.join(__dirname, "..", "node_modules", "naughty-words", "ja.json"));

const API_KEY = process.env.GEMINI_API_KEY;

// 有効なモデルのキャッシュ（プロセス再起動・リロードまで保持）
let cachedValidModels = null;

async function getValidModels(client) {
    if (cachedValidModels) {
        return cachedValidModels;
    }

    try {
        const validModels = new Set();
        const modelsList = await client.models.list();
        for await (const m of modelsList) {
            const methods = m.supportedGenerationMethods || [];
            if (methods.length === 0 || methods.includes("generateContent")) {
                const fullPath = m.name || "";
                const nameWithoutPrefix = fullPath.replace(/^models\//, "");
                validModels.add(fullPath);
                validModels.add(nameWithoutPrefix);
            }
        }
        cachedValidModels = validModels;
        return cachedValidModels;
    } catch (error) {
        console.error("モデル一覧の取得に失敗しました:", error);
        return null;
    }
}

// 配列をシャッフルするヘルパー関数
function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

export default async function handler(request, response) {
    if (request.method !== 'POST') {
        return response.status(405).json({ message: 'Method Not Allowed' });
    }

    const { model: selectedModel, mode = 'default', word = '' } = request.body; // 追加

    // APIキーがない場合はエラー
    if (!API_KEY) {
        return response.status(500).json({ error: "APIキーが設定されていません。" });
    }

    const client = new GoogleGenAI({ apiKey: API_KEY });

    // 選択されたモデルが有効かチェック（Gemini APIから取得したモデル一覧で動的に検証）
    const validModels = await getValidModels(client);
    if (validModels && !validModels.has(selectedModel)) {
        return response.status(400).json({ error: "無効なモデルが選択されました。" });
    }

    const basePrompts = promptsData.map(item => item.prompt);

    const shuffledQuestions = shuffleArray([...questionsData]);
    const limitedQuestions = shuffledQuestions.slice(0, 8); // 例を8個渡す

    const jsonPrompts = limitedQuestions.map(item => {
        if (item.choices) {
            return `${item.question} 回答は選択肢の中から選ぶような形で。`;
        } else {
            return `${item.question} 回答は自由に記述する形で。`;
        }
    });

    const allPrompts = [...basePrompts, ...jsonPrompts];

    const randomIndex = Math.floor(Math.random() * allPrompts.length);
    const selectedPromptTemplate = allPrompts[randomIndex];

    const isChoiceOnly = mode === 'choice_only' || mode === 'custom_word_choice';
    const isCustomWord = mode === 'custom_word' || mode === 'custom_word_choice';

    // ワード指定モードの処理
    let cleanWord = '';
    if (isCustomWord) {
        cleanWord = String(word || '').trim().slice(0, 10);
        if (!cleanWord) {
            return response.status(400).json({ error: "ワードが指定されていません。" });
        }
        // 単語のみ・10文字以内・空白や記号は不可（文章を入れさせない）
        const allowedPattern = /^[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}a-zA-Z0-9ー]{1,10}$/u;
        if (!allowedPattern.test(cleanWord)) {
            return response.status(400).json({ error: "単語のみ・10文字以内で入力してください。" });
        }
        // 汎用NGリスト（naughty-words）でチェック - 最低限
        const hasNg = ngWords.some(w => cleanWord.toLowerCase().includes(w.toLowerCase()));
        // URLや記号の羅列は別途チェック
        const ngPattern = /(https?:\/\/|www\.|[<>{}[\]\\\/])/i;
        if (ngPattern.test(cleanWord) || hasNg) {
            return response.status(400).json({ error: "不適切なワードが含まれています。" });
        }
    }

    const finalPrompt = isCustomWord
        ? (isChoiceOnly
            ? `
    これは、会話や思考を促すための「お題」を生成するタスクです。

    ユーザーが指定したワード「${cleanWord}」を必ず含めて、自然な日本語の疑問文を一つ作成してください。

    以下の質問文は参考例です。参考例をそのまま使用することは禁止です。
    これらを参考に、全く新しい質問文を作成してください。

    例:
        - ${limitedQuestions.map(q => q.question).join('\n- ')}

    回答は必ずJSON形式で返してください。
    {"question":"...？","choices":["...","...","..."]}
    ルール：questionは「${cleanWord}」を含み、自然な日本語の疑問文（？で終わる）、choicesは2〜4個、各15文字以内、どれも選びたくなるバランス、説明文は不要
    `
            : `
    これは、会話や思考を促すための「お題」を生成するタスクです。

    ユーザーが指定したワード「${cleanWord}」を必ず含めて、自然な日本語の疑問文（？で終わる）を一つだけ作成してください。

    以下の質問文は、回答を生成するための参考例です。参考例をそのまま使用することは禁止です。
    これらの質問を参考に、全く新しい質問文を作成してください。

    例:
        - ${limitedQuestions.map(q => q.question).join('\n- ')}

    回答は、お題を自然な日本語の疑問文（？で終わる）にした文章一つだけで、それ以外の説明文や装飾は一切不要です。
    ワード「${cleanWord}」は必ず含めてください。
    `)
        : (isChoiceOnly
            ? `
    これは、会話や思考を促すための「お題」を生成するタスクです。

    ${selectedPromptTemplate}

    以下の質問文は参考例です。参考例をそのまま使用することは禁止です。
    これらを参考に、全く新しい質問文を作成してください。

    例:
        - ${limitedQuestions.map(q => q.question).join('\n- ')}

    回答は必ずJSON形式で返してください。
    {"question":"...？","choices":["...","...","..."]}
    ルール：questionは自然な日本語の疑問文（？で終わる）、choicesは2〜4個、各15文字以内、どれも選びたくなるバランス、定番すぎる話題は避ける、説明文は不要
    `
            : `
    これは、会話や思考を促すための「お題」を生成するタスクです。

    ${selectedPromptTemplate}

    以下の質問文は、回答を生成するための参考例です。参考例をそのまま使用することは禁止です。
    これらの質問を参考に、全く新しい質問文を作成してください。

    例:
        - ${limitedQuestions.map(q => q.question).join('\n- ')}

    回答は、お題を自然な日本語の疑問文（？で終わる）にした文章一つだけで、それ以外の説明文や装飾は一切不要です。
    ただし、「もし超能力が」「もし動物と話せる」「もし好きな仕事（職業）に」のような定番すぎる話題は避けてください。
    `);

    const randomTemperature = Math.random() * 0.5 + 0.5;

    try {
        const generationConfig = {
            temperature: randomTemperature,
        };

        if (isChoiceOnly) {
            generationConfig.responseMimeType = "application/json";
        }

        // Gemma 4またはGemini 3モデルの場合、推論内容（Thinking）を抑制する設定を追加
        if (selectedModel.startsWith("gemma-4") || selectedModel.startsWith("gemini-3")) {
            generationConfig.thinkingConfig = {
                includeThoughts: false,
                // thinkingLevel: "MINIMAL" // 必要に応じて完全に生成を抑制する場合に使用
            };
        }

        let result;
        const maxRetries = 1;
        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                result = await client.models.generateContent({
                    model: selectedModel,
                    contents: finalPrompt,
                    config: generationConfig,
                });
                break;
            } catch (err) {
                const isUnavailable = err?.status === 503 ||
                    err?.message?.includes("503") ||
                    err?.message?.includes("high demand") ||
                    err?.message?.includes("UNAVAILABLE");

                if (isUnavailable && attempt < maxRetries) {
                    console.warn(`モデル高負荷のため再試行します（1秒待機）`);
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    continue;
                }
                throw err;
            }
        }

        // 複数のパーツが返ってきた場合に推論パーツを除外してテキストを取得
        let text = "";
        if (result.candidates && result.candidates[0].content.parts) {
            text = result.candidates[0].content.parts
                .filter(part => !part.thought) // 推論パーツを除外
                .map(part => part.text)
                .join("")
                .trim();
        } else {
            text = result.text;
        }

        if (isChoiceOnly) {
            try {
                const parsed = JSON.parse(text);
                const question = parsed.question || text;
                let choices = Array.isArray(parsed.choices) ? parsed.choices : [];
                // 2〜4個に整形
                if (choices.length > 4) choices = choices.slice(0, 4);
                if (choices.length < 2) choices = [];
                response.status(200).json({ idea: question, choices });
            } catch (e) {
                response.status(200).json({ idea: text });
            }
        } else {
            response.status(200).json({ idea: text });
        }
    } catch (error) {
        console.error('API呼び出しでエラー:', error);
        console.error('エラー詳細:', error.message);

        const isUnavailable = error?.status === 503 ||
            error?.message?.includes("503") ||
            error?.message?.includes("high demand") ||
            error?.message?.includes("UNAVAILABLE");

        if (isUnavailable) {
            response.status(503).json({ error: "現在モデルが混雑しています。しばらく経ってから再度お試しいただくか、他のモデルをお選びください。" });
        } else {
            response.status(500).json({ error: "API呼び出しに失敗しました。" });
        }
    }
}