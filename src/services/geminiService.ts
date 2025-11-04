
import { GoogleGenerativeAI } from '@google/generative-ai';

// TODO: Replace this with a real news API fetch
const getRealtimeNews = async (): Promise<string[]> => {
    return [
        "Fed hints at potential rate hike pause, causing dollar volatility.",
        "UK inflation data comes in hotter than expected, GBP surges.",
        "Japan's central bank maintains ultra-low interest rates, JPY weakens.",
        "US non-farm payroll numbers beat expectations, strengthening the dollar.",
        "Eurozone manufacturing PMI shows slight contraction, weighing on EUR.",
    ];
};

export const getMarketAnalysis = async (apiKey: string): Promise<string> => {
    if (!apiKey) {
        return "Error: Gemini API key not configured. Please go to the Settings page to add your API key.";
    }

    try {
        const ai = new GoogleGenerativeAI(apiKey);

        const model = ai.getGenerativeModel({ model: 'gemini-2.5-flash-preview-09-2025' });
        const newsHeadlines = await getRealtimeNews();
        const prompt = `
            You are a concise financial analyst for a high-frequency scalping trading system.
            Your analysis should be brief, actionable, and focused on short-term sentiment and volatility.
            Analyze the following market news headlines and provide a summary for EUR/USD, GBP/USD, and USD/JPY.
            Format the output as clean markdown. Use bullet points for each currency pair.

            News Headlines:
            - ${newsHeadlines.join('\n- ')}

            Provide a summary of market sentiment and potential scalping opportunities.
        `;

        const result = await model.generateContent(prompt);
        const response = await result.response;
        const text = response.text();

        if (!text) {
            console.error("Gemini response was empty or blocked.");
            return "Error: The AI's response was empty or blocked, possibly due to safety filters.";
        }

        return text;
    } catch (error: any) {
        console.error("Error fetching market analysis from Gemini:", error);
        if (error.message.includes('API key not valid')) {
            return "Error: The provided Gemini API key is not valid. Please check the key in the Settings page.";
        }
        if (error.message.includes('429')) {
            return "Error: Rate limit exceeded for Gemini API. Please wait and try again later.";
        }
        return `Error: Could not retrieve AI market analysis. (${error.message})`;
    }
};


