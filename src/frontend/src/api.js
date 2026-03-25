import axios from 'axios';

const api = axios.create({
  // Use the deployed Render URL if provided, otherwise fallback to local /api proxy
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 30000,
});

export async function fetchGraph(customerId = null, orderId = null) {
  const params = {};
  if (customerId) params.customer_id = customerId;
  if (orderId) params.order_id = orderId;
  const res = await api.get('/graph', { params });
  return res.data;
}

export async function fetchSchema() {
  const res = await api.get('/schema');
  return res.data;
}

export async function queryChat(question, chatHistory = null) {
  const res = await api.post('/query', {
    question,
    chat_history: chatHistory,
  });
  return res.data;
}

export default api;
