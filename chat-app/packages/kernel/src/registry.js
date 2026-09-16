export class Registry {
  #slots = new Map();

  defineSlot(name, { version = '1.0.0', contract = null } = {}) {
    if (this.#slots.has(name)) throw new Error(`slot exists: ${name}`);
    this.#slots.set(name, { version, contract, providers: new Map() });
  }

  register(slotName, id, factory) {
    const slot = this.#slots.get(slotName);
    if (!slot) throw new Error(`unknown slot: ${slotName}`);
    if (slot.providers.has(id)) throw new Error(`duplicate id: ${slotName}/${id}`);
    slot.providers.set(id, factory);
  }

  resolve(slotName, id) {
    const slot = this.#slots.get(slotName);
    if (!slot) throw new Error(`unknown slot: ${slotName}`);
    const f = slot.providers.get(id);
    if (!f) throw new Error(`no provider: ${slotName}/${id}`);
    return f();
  }

  list(slotName) {
    return [...(this.#slots.get(slotName)?.providers.keys() ?? [])];
  }
}
