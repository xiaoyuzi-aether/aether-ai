const env =
  typeof import.meta !== 'undefined' && import.meta.env ? import.meta.env : {};

const DEFAULT_BASE_URL =
  env.VITE_API_BASE_URL || 'http://localhost:8001';
const DEFAULT_MODEL = env.VITE_MODEL || 'deepseek-chat';

function toMessages({ message, history = [] }) {
  const msgs = history
    .filter(h => h && h.role && typeof h.content === 'string')
    .map(h => ({ role: h.role, content: h.content }));
  if (message) msgs.push({ role: 'user', content: message });
  return msgs;
}

export function makeAiHttp({
  baseUrl = DEFAULT_BASE_URL,
  fetchImpl = fetch,
  defaultModel = DEFAULT_MODEL,
} = {}) {
  async function send({ message, history = [], model = defaultModel } = {}) {
    const res = await fetchImpl(`${baseUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: toMessages({ message, history }), model }),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`AI /chat failed: ${res.status} ${text}`);
    }
    const data = await res.json();
    return data.content ?? data.reply ?? '';
  }

  async function sendStreamOnce({
    message,
    history = [],
    model = defaultModel,
    onDelta,
    signal,
  } = {}) {
    const res = await fetchImpl(`${baseUrl}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: toMessages({ message, history }), model }),
      signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`AI /chat/stream failed: ${res.status} ${text}`);
    }
    if (!res.body) throw new Error('ReadableStream not supported');
    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let fullText = '';
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data:')) continue;
            const data = line.slice(5).trim();
            if (data === '[DONE]') return fullText;
            if (!data) continue;
            try {
              const json = JSON.parse(data);
              if (json.error) throw new Error(json.error);
              const delta = json.choices?.[0]?.delta?.content ?? '';
              if (delta) {
                fullText += delta;
                onDelta?.(delta, fullText);
              }
            } catch (e) {
              if (e instanceof Error && e.message) throw e;
            }
          }
        }
      }
    } finally {
      reader.releaseLock?.();
    }
    return fullText;
  }

  async function sendStream(opts, retries = 1) {
    try {
      return await sendStreamOnce(opts);
    } catch (err) {
      if (retries > 0 && !opts?.signal?.aborted) {
        return sendStream(opts, retries - 1);
      }
      throw err;
    }
  }

  return { send, sendStream };
}

export function createHttpAiGateway({ baseUrl, defaultModel } = {}) {
  return makeAiHttp({ baseUrl, defaultModel });
}
