import { marked } from 'marked';
import { Kernel } from '@aether/kernel';
import { makeSendMessage, createChat } from '@aether/core';
import { createLocalChatRepository } from '@aether/adapter-storage-local';
import { createHttpAiGateway } from '@aether/adapter-ai-http';
import { createBrowserFileStore } from '@aether/adapter-file-browser';
import { MarkdownPlugin } from '@aether/plugin-markdown';
import { AttachmentPlugin } from '@aether/plugin-attachment';
import { MultiSelectPlugin } from '@aether/plugin-multi-select';
import { mountApp } from './app.js';

const kernel = new Kernel({ version: '1.0.0' });
const chatRepo = createLocalChatRepository();
const aiGateway = createHttpAiGateway({ baseUrl: 'http://localhost:8001' });
const fileStore = createBrowserFileStore();
const sendMessage = makeSendMessage({ chatRepo, aiGateway, bus: kernel.bus });

kernel.use(MarkdownPlugin({ renderer: (t) => marked.parse(t || '') }));
kernel.use(AttachmentPlugin({ fileStore }));
kernel.use(MultiSelectPlugin());

await kernel.start();
mountApp({ kernel, chatRepo, createChat, sendMessage });
