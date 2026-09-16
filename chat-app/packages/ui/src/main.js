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
import { mountApp } from './app.js';

async function main() {
  const kernel = new Kernel({ version: '1.0.0' });
  const chatRepo = createLocalChatRepository();
  const aiGateway = createHttpAiGateway({ baseUrl: 'http://localhost:8001' });
  const fileStore = createBrowserFileStore();
  const sendMessage = makeSendMessage({ chatRepo, aiGateway, bus: kernel.bus });

  kernel.use(MarkdownPlugin({ renderer: (t) => marked.parse(t || '') }));
  kernel.use(AttachmentPlugin({ fileStore }));
  kernel.use(MultiSelectPlugin());

  await kernel.start();
  mountApp({ kernel, chatRepo, createChat, sendMessage, aiGateway });
}

main().catch(e => { console.error('[aether] boot failed', e); });


