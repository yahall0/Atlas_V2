// Ambient module declarations for stylesheet side-effect imports.
//
// Next.js handles CSS at bundle time, so the runtime works without a
// type. But some IDE TypeScript configurations (particularly with the
// `noUncheckedSideEffectImports` lint hint enabled) flag these imports
// because there is no `.d.ts` declaring them.
//
// This file makes those side-effect imports type-safe to the IDE
// without changing runtime behaviour.

declare module '*.css';
declare module 'reactflow/dist/style.css';
