export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function downloadString(
  content: string,
  filename: string,
  mime: string,
): void {
  downloadBlob(new Blob([content], { type: mime }), filename);
}

function findFirstSvg(container: HTMLElement | null): SVGSVGElement | null {
  if (!container) return null;
  return container.querySelector('svg');
}

export function exportContainerSvg(
  container: HTMLElement | null,
  filename: string,
): void {
  const svg = findFirstSvg(container);
  if (!svg) throw new Error('SVG not found');
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  const xml = new XMLSerializer().serializeToString(clone);
  downloadString(xml, filename, 'image/svg+xml');
}

export async function exportContainerPng(
  container: HTMLElement | null,
  filename: string,
): Promise<void> {
  const svg = findFirstSvg(container);
  if (!svg) throw new Error('SVG not found');
  const rect = svg.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clone.setAttribute('width', String(width));
  clone.setAttribute('height', String(height));
  const xml = new XMLSerializer().serializeToString(clone);
  const svg64 = btoa(unescape(encodeURIComponent(xml)));
  const dataUrl = `data:image/svg+xml;base64,${svg64}`;
  await new Promise<void>((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Canvas 2D context unavailable'));
        return;
      }
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, width, height);
      ctx.drawImage(img, 0, 0, width, height);
      canvas.toBlob((blob) => {
        if (!blob) {
          reject(new Error('PNG encode failed'));
          return;
        }
        downloadBlob(blob, filename);
        resolve();
      }, 'image/png');
    };
    img.onerror = () => reject(new Error('SVG render failed'));
    img.src = dataUrl;
  });
}

export function rowsToCsv(
  rows: Record<string, unknown>[],
  columns: string[],
): string {
  const header = columns.map(escapeCsv).join(',');
  const body = rows
    .map((row) =>
      columns
        .map((col) => {
          const v = row[col];
          if (v === null || v === undefined) return '';
          if (typeof v === 'number' || typeof v === 'boolean') {
            return escapeCsv(String(v));
          }
          if (typeof v === 'string') {
            return escapeCsv(v);
          }
          return '';
        })
        .join(','),
    )
    .join('\n');
  return `${header}\n${body}`;
}

function escapeCsv(value: string): string {
  if (/[",\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}
