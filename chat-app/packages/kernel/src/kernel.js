import { EventBus } from './event-bus.js';
import { Registry } from './registry.js';

export class Kernel {
  constructor({ version = '1.0.0' } = {}) {
    this.version = version;
    this.bus = new EventBus();
    this.registry = new Registry();
    this.plugins = new Map();
    this.state = 'created';
  }

  async start() {
    if (this.state !== 'created') return;
    this.state = 'starting';
    this.bus.emit('kernel:starting', { version: this.version });
    for (const p of this.plugins.values()) await this.#safe('setup', p);
    for (const p of this.plugins.values()) await this.#safe('start', p);
    this.state = 'running';
    this.bus.emit('kernel:started', { version: this.version });
  }

  async stop() {
    this.state = 'stopping';
    for (const p of [...this.plugins.values()].reverse()) await this.#safe('stop', p);
    this.state = 'stopped';
    this.bus.emit('kernel:stopped', {});
  }

  use(plugin) {
    if (!plugin?.name) throw new Error('plugin.name required');
    if (this.plugins.has(plugin.name)) throw new Error(`plugin exists: ${plugin.name}`);
    if (this.state !== 'created') throw new Error('use() must be called before start()');
    this.plugins.set(plugin.name, plugin);
    return this;
  }

  async #safe(hook, plugin) {
    const fn = plugin[hook];
    if (typeof fn !== 'function') return;
    try { await fn(this); }
    catch (e) { console.error(`[kernel] plugin ${plugin.name} ${hook} failed`, e); }
  }
}
