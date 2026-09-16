import { createMessage } from '../domain/message.js';
import { appendMessage } from '../domain/chat.js';

export function makeSendMessage({ chatRepo, aiGateway, bus }) {
  return async function sendMessage(chat, text, attachments = []) {
    const userMsg = createMessage({ role: 'user', content: text, attachments });
    appendMessage(chat, userMsg);
    await chatRepo.save(chat);
    bus.emit('chat:message:added', { chat, message: userMsg });
    bus.emit('chat:ai:request', { chatId: chat.id });

    let reply;
    try {
      reply = await aiGateway.send({
        message: text,
        history: chat.messages.slice(0, -1),
      });
    } catch (e) {
      bus.emit('chat:ai:error', { chatId: chat.id, error: e });
      throw e;
    }

    const aiMsg = createMessage({ role: 'assistant', content: reply });
    appendMessage(chat, aiMsg);
    await chatRepo.save(chat);
    bus.emit('chat:message:added', { chat, message: aiMsg });
    return aiMsg;
  };
}
