export const AETHER_API_VERSION = '1.0.0';
export { Kernel } from '@aether/kernel';
export { createChat, createMessage, makeSendMessage, makeSendMessageStream } from '@aether/core';
export { createLocalChatRepository } from '@aether/adapter-storage-local';
export { createHttpAiGateway } from '@aether/adapter-ai-http';
export { createBrowserFileStore } from '@aether/adapter-file-browser';
