import { GoogleGenerativeAI } from "@google/generative-ai";

// Vercelに設定した環境変数を取得
const API_KEY = process.env.GEMINI_API_KEY;
const genAI = new GoogleGenerativeAI(API_KEY);

export default async function handler(request, response) {
    if (request.method !== 'POST') {
        return response.status(405).json({ message: 'Method Not Allowed' });
    }

    const prompt = "今すぐ使える、複数人の会話で盛り上がるための面白いお題を一つだけ提案してください。回答は、お題そのものだけで、余計な説明や前書き、後書き、記号などは一切不要です。";

    try {
        const model = genAI.getGenerativeModel({ model: "gemini-pro" });
        const result = await model.generateContent(prompt);
        const text = result.response.text;
        
        response.status(200).json({ idea: text });
    } catch (error) {
        console.error(error);
        response.status(500).json({ error: "Failed to generate idea." });
    }
}