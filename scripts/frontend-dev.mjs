import { createServer, request as httpRequest } from "node:http";
import { createReadStream, existsSync, mkdirSync, readFileSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import esbuild from "../frontend/node_modules/esbuild/lib/main.js";

const root = resolve(new URL("..", import.meta.url).pathname);
const frontend = join(root, "frontend");
const outdir = join(frontend, ".dev");
const port = Number(process.env.FRONTEND_PORT || 5173);
const apiTarget = process.env.API_TARGET || "http://127.0.0.1:8000";

mkdirSync(join(outdir, "assets"), { recursive: true });

const ctx = await esbuild.context({
  entryPoints: [join(frontend, "src/main.tsx")],
  bundle: true,
  outfile: join(outdir, "assets/main.js"),
  sourcemap: true,
  format: "esm",
  jsx: "automatic",
  loader: {
    ".svg": "dataurl"
  },
  define: {
    "process.env.NODE_ENV": JSON.stringify("development")
  }
});

await ctx.watch();

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".map": "application/json; charset=utf-8"
};

function proxyApi(req, res) {
  const target = new URL(req.url, apiTarget);
  const proxy = httpRequest(
    target,
    {
      method: req.method,
      headers: { ...req.headers, host: target.host }
    },
    (apiRes) => {
      res.writeHead(apiRes.statusCode || 502, apiRes.headers);
      apiRes.pipe(res);
    }
  );
  proxy.on("error", () => {
    res.writeHead(502, { "content-type": "application/json" });
    res.end(JSON.stringify({ detail: "Backend API is not reachable on " + apiTarget }));
  });
  req.pipe(proxy);
}

function serveIndex(res) {
  const cssTag = existsSync(join(outdir, "assets/main.css"))
    ? '<link rel="stylesheet" href="/assets/main.css" />'
    : "";
  const html = readFileSync(join(frontend, "index.html"), "utf8").replace(
    '<script type="module" src="/src/main.tsx"></script>',
    `${cssTag}\n    <script type="module" src="/assets/main.js"></script>`
  );
  res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  res.end(html);
}

createServer((req, res) => {
  if (!req.url) {
    res.writeHead(400);
    res.end();
    return;
  }
  if (req.url.startsWith("/api/")) {
    proxyApi(req, res);
    return;
  }
  if (req.url === "/" || req.url.startsWith("/?")) {
    serveIndex(res);
    return;
  }
  const cleanPath = decodeURIComponent(req.url.split("?")[0]).replace(/^\/+/, "");
  const filePath = join(outdir, cleanPath);
  if (!filePath.startsWith(outdir) || !existsSync(filePath)) {
    serveIndex(res);
    return;
  }
  res.writeHead(200, { "content-type": contentTypes[extname(filePath)] || "application/octet-stream" });
  createReadStream(filePath).pipe(res);
}).listen(port, "0.0.0.0", () => {
  console.log(`Frontend dev server running at http://localhost:${port}`);
  console.log(`Proxying /api to ${apiTarget}`);
});

