import { describe, it, expect, vi } from 'vitest';
import { makeSendMessageStream } from '@aether/core';

describe('sendMessageStream usecase', () => {
  it('writes user msg, calls ai stream, saves, emits events', async () => {
    const events = [];
    const bus = { emit: (e, p) => events.push([e, p]) };
    const chat = { id: 'c1', messages: [], updatedAt: 0 };
    const chatRepo = { save: vi.fn().mockResolvedValue(undefined) };
    const aiGateway = {
      sendStream: vi.fn(async (_payload, onDelta) => {
        onDelta?.('你', '你');
        onDelta?.('好', '你好');
        return '你好';
      }),
    };

    const send = makeSendMessageStream({ chatRepo, aiGateway, bus });
    const result = await send(chat, 'hi', [], () => {});

    expect(result.content).toBe('你好');
    expect(chat.messages.some(m => m.role === 'user' && m.content === 'hi')).toBe(true);
    expect(chat.messages.some(m => m.role === 'assistant' && m.content === '你好')).toBe(true);
    expect(chatRepo.save).toHaveBeenCalled();
    expect(events.some(([e]) => e === 'chat:message:added')).toBe(true);
  });
});
