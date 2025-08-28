import { GoogleGenerativeAI } from "@google/generative-ai";

const API_KEY = process.env.GEMINI_API_KEY;
const MODEL_NAME = "gemini-2.5-flash-lite"; // モデル名を定数として宣言
const genAI = new GoogleGenerativeAI(API_KEY);

export default async function handler(request, response) {
    if (request.method !== 'POST') {
        return response.status(405).json({ message: 'Method Not Allowed' });
    }

    const prompts = [
        // 基本的な盛り上がりお題
        "複数人の会話で盛り上がるための面白い質問文を一つだけ提案してください。",
        "飲み会や雑談で使える、少し変わった質問文を一つだけ提案してください。",
        "友人と盛り上がる、予想外の答えが返ってくるような質問文を一つだけ教えてください。",

        // 身近で話しやすいお題
        "日常生活の中で誰もが共感できるような、気軽に話せる質問文を一つだけ提案してください。",
        "学生時代や社会人生活での体験談で盛り上がりそうな質問文を一つだけ考えてください。",
        "子供の頃の思い出を引き出すような、懐かしい質問文を一つだけ教えてください。",
        "食べ物や料理に関する、みんなで議論したくなる質問文を一つだけ提案してください。",
        "最近ハマっている趣味や好きなことについて語りたくなる質問文を一つだけ考えてください。",

        // 軽めの比較・選択系
        "AかBかで選ぶような、軽く議論できる質問文を一つだけ提案してください。",

        // エピソード・自己分析系
        "今まで経験した中で印象的だった出来事を聞き出せる質問文を一つだけ考えてください。",
        "自分の性格や特徴を楽しく紹介できる質問文を一つだけ提案してください。",

        // 未来・目標系
        "将来の夢や目標について気軽に語れる質問文を一つだけ提案してください。",
        "来年やってみたいことを話したくなる質問文を一つだけ考えてください。",

        // 思考・想像力系
        "歴史上の人物に関する、会話が盛り上がる質問文を一つだけ提案してください。",
        "もしもシリーズで、面白いシチュエーションを提示し、参加者が具体的に答えられるような質問文を一つだけ提案してください。"
    ];

    const randomIndex = Math.floor(Math.random() * prompts.length);
    const prompt = prompts[randomIndex] + "回答は、お題を自然な日本語の疑問文（？で終わる）にした文章一つだけで、それ以外の説明文や装飾は一切不要です。ただし、超能力、もしも動物と話せる、もしも明日から〜のような定番すぎる話題は避けてください。";
    const randomTemperature = Math.random() * 0.5 + 0.5;

    try {
        const model = genAI.getGenerativeModel({
            model: MODEL_NAME, // 定数を使用
            generationConfig: {
                temperature: randomTemperature,
            },
        });
        const result = await model.generateContent(prompt);
        const text = result.response.text();

        response.status(200).json({ idea: text });
    } catch (error) {
        console.error('API呼び出しでエラー:', error);
        console.error('エラー詳細:', error.message);
        response.status(500).json({ error: "API呼び出しに失敗しました。" });
    }
}