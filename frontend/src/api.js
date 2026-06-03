import axios from "axios";

const api = axios.create({
  baseURL: "https://ecoprompt-backend-1078329158947.asia-south1.run.app",
});

export const runPrompt = async (prompt) => {
  const res = await api.post("/generate", { prompt });
  return res.data;
};