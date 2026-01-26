declare module 'react-markdown' {
  import type { ComponentType, ReactNode } from 'react';

  export interface ReactMarkdownProps {
    children?: string;
    className?: string;
    remarkPlugins?: unknown[];
    components?: Record<string, ComponentType<{ children?: ReactNode }>>;
  }

  const ReactMarkdown: ComponentType<ReactMarkdownProps>;
  export default ReactMarkdown;
}
