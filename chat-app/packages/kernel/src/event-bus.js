export class EventBus {
  #handlers = new Map();

  on(event, handler) {
    if (!this.#handlers.has(event)) this.#handlers.set(event, new Set());
    this.#handlers.get(event).add(handler);
    return () => this.off(event, handler);
  }

  once(event, handler) {
    const off = this.on(event, (payload) => { off(); handler(payload); });
    return off;
  }

  off(event, handler) {
    this.#handlers.get(event)?.delete(handler);
  }

  emit(event, payload) {
    this.#handlers.get(event)?.forEach(h => this.#safe(h, payload));
    for (const [pattern, handlers] of this.#handlers) {
      if (pattern === event) continue;
      if (pattern.includes('*') && this.#match(pattern, event)) {
        handlers.forEach(h => this.#safe(h, payload));
      }
    }
  }

  #safe(h, payload) {
    try { h(payload); } catch (e) { console.error('[event-bus]', e); }
  }

  #match(pattern, event) {
    const re = new RegExp('^' + pattern.replace(/\*/g, '.*') + '$');
    return re.test(event);
  }
}
