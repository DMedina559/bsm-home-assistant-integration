/** Build deterministic local ES modules; HACS installs the committed output. */
import { build } from "esbuild";
import { readdir, readFile, writeFile, unlink } from "node:fs/promises";
import path from "node:path";
const outdir = "custom_components/bedrock_server_manager/frontend";
const entries = (await readdir("frontend/src"))
  .filter((name) => /^bsm-.*-card\.js$/.test(name))
  .map((name) => `frontend/src/${name}`);
const result = await build({
  entryPoints: entries,
  outdir,
  bundle: true,
  splitting: true,
  format: "esm",
  target: "es2022",
  minify: true,
  legalComments: "linked",
  write: false,
  chunkNames: "shared-[hash]",
  define: { "process.env.NODE_ENV": '"production"' },
});
const files = new Map(
  result.outputFiles.map((file) => [path.basename(file.path), file.contents]),
);
if (process.argv.includes("--check")) {
  const actual = (await readdir(outdir)).filter(
    (file) =>
      /\.(js|LEGAL\.txt)$/.test(file) && file !== "bsm-npm-overview-card.js",
  );
  for (const name of actual)
    if (!files.has(name)) throw Error(`Obsolete frontend bundle: ${name}`);
  for (const [name, contents] of files) {
    if (!Buffer.from(contents).equals(await readFile(path.join(outdir, name))))
      throw Error(`Frontend bundle drift: ${name}`);
  }
} else {
  for (const name of await readdir(outdir))
    if (
      /\.(js|LEGAL\.txt)$/.test(name) &&
      name !== "bsm-npm-overview-card.js" &&
      !files.has(name)
    )
      await unlink(path.join(outdir, name));
  for (const [name, contents] of files)
    await writeFile(path.join(outdir, name), contents);
}
console.log(
  `${files.size} local frontend files ${process.argv.includes("--check") ? "verified" : "built"}.`,
);
