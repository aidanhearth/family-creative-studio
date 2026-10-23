import {build} from 'esbuild';
import fs from 'node:fs';
fs.mkdirSync('dist',{recursive:true});
for (const entry of ['app','viewer']) await build({entryPoints:[`web/${entry}.js`],bundle:true,format:'iife',outfile:`dist/${entry}.js`,minify:true,legalComments:'linked'});
await build({entryPoints:['vendor/storytold--artcraft/HistoryManager.ts'],bundle:true,platform:'node',format:'esm',outfile:'dist/history.mjs'});
