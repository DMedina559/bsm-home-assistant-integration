// Copy the installed npm import graph into self-hosted browser modules.
// JSON modules become ordinary JS for browsers without import attributes.
import { readFile, mkdir, writeFile, readdir } from "node:fs/promises";
import { dirname, resolve, relative, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const output = resolve(root, "custom_components/bedrock_server_manager/frontend");
const generated = new Map();
const versions = JSON.parse(await readFile(resolve(root, "package.json"))).dependencies;

async function visit(source, target) {
  if (generated.has(target)) return;
  generated.set(target, "");
  let text = await readFile(source, "utf8");
  if (source.endsWith(".json")) text = `export default ${JSON.stringify(JSON.parse(text))};\n`;
  const imports = [...text.matchAll(/\b(?:from\s*|import\s*)["']([^"']+)["'](?:\s+with\s*\{\s*type:\s*["']json["']\s*\})?/g)];
  for (const match of imports.reverse()) {
    const specifier = match[1];
    let dependency, destination;
    if (specifier.startsWith("@bedrock-server-manager/")) {
      const parts = specifier.split("/");
      const name = parts.slice(0, 2).join("/");
      const packageRoot = resolve(root, "node_modules", name);
      const manifest = JSON.parse(await readFile(join(packageRoot, "package.json")));
      if (manifest.version !== versions[name]) throw Error(`Unexpected version for ${name}`);
      const entry = manifest.exports[parts.length === 2 ? "." : `./${parts.slice(2).join("/")}`];
      dependency = resolve(packageRoot, typeof entry === "string" ? entry : entry.default);
      destination = join(output, "overview-vendor", parts[1], relative(join(packageRoot, "dist"), dependency));
    } else if (specifier.startsWith(".")) {
      dependency = resolve(dirname(source), specifier);
      destination = resolve(dirname(target), specifier);
    } else throw Error(`Unsupported browser import: ${specifier}`);
    if (dependency.endsWith(".json")) destination += ".js";
    const rewritten = `./${relative(dirname(target), destination).replaceAll("\\", "/")}`;
    text = text.slice(0, match.index) + match[0].replace(/(["'])[^"']+\1(?:\s+with\s*\{[^}]+\})?$/, JSON.stringify(rewritten)) + text.slice(match.index + match[0].length);
    await visit(dependency, destination);
  }
  generated.set(target, text);
}

await visit(resolve(root, "frontend/src/bsm-overview-card.js"), join(output, "bsm-overview-card.js"));
generated.set(join(output, "overview-vendor/LICENSE"), await readFile(resolve(root, "frontend/vendor-LICENSE"), "utf8"));
if (process.argv.includes("--check")) {
  for (const [path, content] of generated) {
    if (await readFile(path, "utf8").catch(() => null) !== content) throw Error(`Run npm run build: ${relative(root, path)}`);
  }
  const existing = await readdir(join(output, "overview-vendor"), { recursive: true, withFileTypes: true });
  for (const file of existing.filter((entry) => entry.isFile())) {
    const path = join(file.parentPath, file.name);
    if (!generated.has(path)) throw Error(`Obsolete generated module: ${path}`);
  }
} else {
  for (const [path, content] of generated) {
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, content);
  }
}
console.log(`Verified ${generated.size} self-hosted card modules`);
