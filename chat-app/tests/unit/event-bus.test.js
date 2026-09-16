import { describe, it, expect, vi } from 'vitest';
import { createEventBus } from '@aether/kernel';

describe('EventBus', () => {
  it('on/emit works', () => {
    const bus = createEventBus();
    const fn = vi.fn();
    bus.on('foo', fn);
    bus.emit('foo', 1);
    expect(fn).toHaveBeenCalledWith(1);
  });

  it('wildcard subscription works', () => {
    const bus = createEventBus();
    const fn = vi.fn();
    bus.on('plugin:*', fn);
    bus.emit('plugin:loaded', { name: 'markdown' });
    expect(fn).toHaveBeenCalled();
  });

  it('handler error does not break others', () => {
    const bus = createEventBus();
    const ok = vi.fn();
    bus.on('foo', () => { throw new Error('bad'); });
    bus.on('foo', ok);
    expect(() => bus.emit('foo')).not.toThrow();
    expect(ok).toHaveBeenCalled();
  });
});
