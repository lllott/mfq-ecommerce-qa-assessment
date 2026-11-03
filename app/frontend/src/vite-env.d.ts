/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PRODUCT_ID?: string;
  readonly VITE_API_PROXY_TARGET?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
