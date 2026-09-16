export function createHttpAiGateway({ baseUrl = 'http://localhost:8001' } = {}) {
  return {
    async send({ message, history }) {
      const r = await fetch(`${baseUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, history }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      return data.reply || '';
    },

    // 流式：onDelta(deltaText) 逐块回调
    async sendStream({ message, history }, onDelta) {
      const r = await fetch(`${baseUrl}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, history }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      let full = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const blocks = buf.split('\n\n');
        buf = blocks.pop() || '';
        for (const block of blocks) {
          const line = block.replace(/^data:\s*/, '');
          if (!line || line === '[DONE]') continue;
          try {
            const j = JSON.parse(line);
            const delta = j.choices?.[0]?.delta?.content || '';
            if (delta) { full += delta; onDelta(delta); }
          } catch { /* keep-alive 注释等忽略 */ }
        }
      }
      return full;
    },
  };
}
