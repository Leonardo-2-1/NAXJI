import { readFile, writeFile } from 'node:fs/promises';
import { gzipSync } from 'node:zlib';
import { preview } from 'vite';
const phase = process.argv[2];
const manifest = JSON.parse(await readFile('dist/.vite/manifest.json', 'utf8'));
const initial = new Set(['index.html']);
function visit(key) {
  const entry = manifest[key];
  initial.add(entry.file);
  for (const css of entry.css || []) initial.add(css);
  for (const imported of entry.imports || []) visit(imported);
}
visit('index.html');
const server = await preview({ logLevel: 'error', preview: { host: '127.0.0.1', port: 5188, strictPort: true } });
try {
  const resources = [];
  for (const file of initial) {
    const bytes = await readFile('dist/' + file);
    resources.push({ file, bytes: bytes.length, gzip_bytes: gzipSync(bytes).length });
  }
  const runs = [];
  for (let i = 0; i < 3; i++) {
    const start = performance.now();
    const statuses = await Promise.all([...initial].map(async file => {
      const response = await fetch('http://127.0.0.1:5188/' + file, { cache: 'no-store' });
      await response.arrayBuffer();
      return response.status;
    }));
    runs.push({ ms: +(performance.now() - start).toFixed(2), statuses });
  }
  const data = { phase, scope: 'HTTP loopback, build producción, recursos iniciales estáticos; no mide FCP/LCP ni parseo/render del navegador',
    resources, bytes: resources.reduce((n,r) => n+r.bytes,0), gzip_bytes: resources.reduce((n,r) => n+r.gzip_bytes,0), runs };
  await writeFile(`docs/evidencias/login-${phase}-recursos.json`, JSON.stringify(data, null, 2));
  console.log(JSON.stringify(data));
} finally { await new Promise(resolve => server.httpServer.close(resolve)); }
// Ejecutar tras npm run build -- --manifest. Sirve solo el build en loopback
// durante tres descargas; excluye importaciones dinámicas del arranque público.
