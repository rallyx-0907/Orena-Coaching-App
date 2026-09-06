import vm from 'node:vm';
import fs from 'node:fs';
import path from 'node:path';

const projectRoot = path.resolve(process.argv[2] || '.');
const root = path.join(projectRoot, 'static', 'orena');
const entry = path.join(root, 'app.js');
const cache = new Map();

async function load(file) {
  file = path.resolve(file);
  if (cache.has(file)) return await cache.get(file);

  const pending = (async () => {
    if (!fs.existsSync(file)) {
      throw new Error(`Missing browser module: ${file}`);
    }

    const code = fs.readFileSync(file, 'utf8');
    let mod;
    try {
      mod = new vm.SourceTextModule(code, { identifier: file });
    } catch (error) {
      throw new Error(`Browser ESM parse failed in ${file}: ${error.message}`);
    }

    await mod.link(async (specifier, ref) => {
      if (!specifier.startsWith('.')) {
        throw new Error(`Unexpected external module "${specifier}" imported by ${ref.identifier}`);
      }

      const cleanSpecifier = specifier.replace(/[?#].*$/, '');
      const child = path.resolve(path.dirname(ref.identifier), cleanSpecifier);
      return await load(child);
    });

    return mod;
  })();

  cache.set(file, pending);
  return await pending;
}

try {
  await load(entry);
  console.log(`Orena browser ESM graph validation OK (${cache.size} modules linked)`);
} catch (error) {
  console.error('Orena browser ESM graph validation FAILED');
  console.error(error?.stack || error);
  process.exit(1);
}
