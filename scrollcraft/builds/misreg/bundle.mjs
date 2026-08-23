/* Bundles the build into one self-contained HTML file for publishing.
   Inlines both stylesheets, both scripts and the two woff2 faces as data URIs,
   and strips the document skeleton, because the Artifact host supplies it.
   Run: node bundle.mjs */
import fs from "node:fs";

const html = fs.readFileSync("index.html", "utf8");
const engineCss = fs.readFileSync("scrollcraft.css", "utf8");
const engineJs = fs.readFileSync("scrollcraft.js", "utf8");
let pageCss = fs.readFileSync("page.css", "utf8");

const b64 = (p) => fs.readFileSync(p).toString("base64");
pageCss = pageCss
  .replace('url("fonts/archivo-black.woff2")',
           `url("data:font/woff2;base64,${b64("fonts/archivo-black.woff2")}")`)
  .replace('url("fonts/space-grotesk.woff2")',
           `url("data:font/woff2;base64,${b64("fonts/space-grotesk.woff2")}")`);

let body = html.split("<body>")[1].split("</body>")[0];
const pageScript = body.split("<script>")[1].split("<\/script>")[0];
body = body.replace(/<script[\s\S]*?<\/script>/g, "").trim();

const out = `<title>Misregister Press</title>
<style>
${engineCss}
${pageCss}
</style>

${body}

<script>
${engineJs}
<\/script>
<script>
${pageScript}
<\/script>
`;

fs.writeFileSync("artifact.html", out);
console.log(`artifact.html  ${(out.length / 1024).toFixed(0)}KB`);
