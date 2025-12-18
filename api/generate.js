import { GoogleGenerativeAI } from "@google/generative-ai";
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

const API_KEY = process.env.GEMINI_API_KEY;

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

    const { model: selectedModel } = request.body; // 追加

    // APIキーがない場合はエラー
    if (!API_KEY) {
        return response.status(500).json({ error: "APIキーが設定されていません。" });
    }
    
    // 選択されたモデルが有効かチェック
    const validModels = [
        // Gemma
        "gemma-3-27b-it",
        "gemma-3-12b-it",
        "gemma-3-4b-it",
        "gemma-3-1b-it",
        // Gemini
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-3-flash-preview",
    ];
    if (!validModels.includes(selectedModel)) {
        return response.status(400).json({ error: "無効なモデルが選択されました。" });
    }
    
    const genAI = new GoogleGenerativeAI(API_KEY);

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
    
    const finalPrompt = 
    `
    これは、会話や思考を促すための「お題」を生成するタスクです。

    ${selectedPromptTemplate}

    以下の質問文は、回答を生成するための参考例です。参考例をそのまま使用することは禁止です。
    これらの質問を参考に、全く新しい質問文を作成してください。

    例:
    - ${limitedQuestions.map(q => q.question).join('\n- ')}

    回答は、お題を自然な日本語の疑問文（？で終わる）にした文章一つだけで、それ以外の説明文や装飾は一切不要です。
    ただし、「もし超能力が」「もし動物と話せる」「もし好きな仕事（職業）に」のような定番すぎる話題は避けてください。
    `;
    
    const randomTemperature = Math.random() * 0.5 + 0.5;

    try {
        const model = genAI.getGenerativeModel({
            model: selectedModel, // 修正
            generationConfig: {
                temperature: randomTemperature,
            },
        });
        const result = await model.generateContent(finalPrompt);
        const text = result.response.text();

        response.status(200).json({ idea: text });
    } catch (error) {
        console.error('API呼び出しでエラー:', error);
        console.error('エラー詳細:', error.message);
        response.status(500).json({ error: "API呼び出しに失敗しました。" });
    }
}