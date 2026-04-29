/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module 'plotly.js-cartesian-dist-min' {
  import type Plotly from 'plotly.js';
  const value: typeof Plotly;
  export default value;
}

declare module 'react-plotly.js/factory' {
  import type { ComponentType } from 'react';
  import type Plotly from 'plotly.js';
  import type { PlotParams } from 'react-plotly.js';
  export default function createPlotlyComponent(
    plotly: typeof Plotly,
  ): ComponentType<PlotParams>;
}
