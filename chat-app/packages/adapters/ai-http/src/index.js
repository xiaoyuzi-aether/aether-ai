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
  };
}
