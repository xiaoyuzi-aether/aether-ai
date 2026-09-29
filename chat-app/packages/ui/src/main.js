import { marked } from 'marked';
import {
  Kernel,
  createChat,
  makeSendMessage,
  createLocalChatRepository,
  createHttpAiGateway,
  createBrowserFileStore,
} from '@aether/public-api';
import { MarkdownPlugin } from '@aether/plugin-markdown';
import { AttachmentPlugin } from '@aether/plugin-attachment';
import { MultiSelectPlugin } from '@aether/plugin-multi-select';
import installContentFetcher from '@aether/plugin-content-fetcher';
import installContentPipeline from '@aether/plugin-content-pipeline';
import installGeoAnalyzer from '@aether/plugin-geo-analyzer';
import { mountApp } from './app.js';

async function main() {
  const kernel = new Kernel({ version: '1.0.0' });
  const chatRepo = createLocalChatRepository();
  const aiGateway = createHttpAiGateway();
  const fileStore = createBrowserFileStore();
  const sendMessage = makeSendMessage({ chatRepo, aiGateway, bus: kernel.bus });

  kernel.use(MarkdownPlugin({ renderer: (t) => marked.parse(t || '') }));
  kernel.use(AttachmentPlugin({ fileStore }));
  kernel.use(MultiSelectPlugin());

  // GEO 插件适配：新插件直接用 kernel.on/emit/defineSlot/register，
  // 这里代理到现有 kernel.bus / kernel.registry，不改插件代码
  kernel.on = (e, h) => kernel.bus.on(e, h);
  kernel.once = (e, h) => kernel.bus.once(e, h);
  kernel.emit = (e, p) => kernel.bus.emit(e, p);
  kernel.defineSlot = (name, opts) => kernel.registry.defineSlot(name, opts);
  kernel.register = (slot, id, factory) => kernel.registry.register(slot, id, factory);
  kernel.resolve = (slot, id) => kernel.registry.resolve(slot, id);
  kernel.list = (slot) => kernel.registry.list(slot);

  installContentFetcher(kernel);
  installContentPipeline(kernel);
  installGeoAnalyzer(kernel);

  await kernel.start();
  mountApp({ kernel, chatRepo, createChat, sendMessage, aiGateway });
}

main().catch(e => { console.error('[aether] boot failed', e); });


