import { rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
rmSync(path.join(appRoot, "dist"), { recursive: true, force: true });

