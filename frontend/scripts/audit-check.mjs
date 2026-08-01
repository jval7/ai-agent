#!/usr/bin/env node
/**
 * Gate de seguridad para dependencias de produccion.
 *
 * Reemplaza a `npm audit --audit-level=high`, que no permite exceptuar
 * advisories puntuales. Hizo falta porque react-router no tiene ninguna version
 * libre de avisos: <= 7.11.0 arrastra los open redirect y 7.18.x (la ultima)
 * reporta un CSRF que solo afecta al modo RSC.
 *
 * El gate sigue fallando ante cualquier vulnerabilidad high o critical; solo
 * deja pasar los IDs de ALLOWED, cada uno con su motivo y su condicion de
 * salida. Una excepcion sin revisar es peor que no tener gate: si alguna deja
 * de aplicar, se borra de la lista y el gate vuelve a cubrirla.
 */

import { execFileSync } from "node:child_process";

const ALLOWED = [
  {
    id: "GHSA-qwww-vcr4-c8h2",
    package: "react-router",
    reason:
      "CSRF en RSC Mode. La app es una SPA con BrowserRouter: no usa React Server Components, " +
      "ni SSR, ni el runtime RSC de react-router, asi que el vector no existe aca.",
    removeWhen: "react-router publique una version > 8.2.0 y se actualice el paquete."
  }
];

const BLOCKING_SEVERITIES = new Set(["high", "critical"]);

function runAudit() {
  try {
    return execFileSync("npm", ["audit", "--json", "--omit=dev"], {
      encoding: "utf8",
      maxBuffer: 20 * 1024 * 1024
    });
  } catch (error) {
    // npm audit sale con codigo != 0 cuando encuentra vulnerabilidades; la
    // salida JSON viene igual por stdout y es lo que necesitamos analizar.
    if (typeof error.stdout === "string" && error.stdout.trim() !== "") {
      return error.stdout;
    }
    throw error;
  }
}

function collectAdvisories(report) {
  const advisories = new Map();
  for (const vulnerability of Object.values(report.vulnerabilities ?? {})) {
    for (const source of vulnerability.via ?? []) {
      // Las entradas string son nombres de paquetes (dependencias
      // transitivas); el advisory real vive en la entrada de ese paquete.
      if (typeof source !== "object" || source.url === undefined) {
        continue;
      }
      if (!BLOCKING_SEVERITIES.has(source.severity)) {
        continue;
      }
      const id = source.url.split("/").pop();
      advisories.set(id, {
        id,
        package: source.name,
        title: source.title,
        severity: source.severity,
        url: source.url
      });
    }
  }
  return [...advisories.values()];
}

const report = JSON.parse(runAudit());
const blocking = collectAdvisories(report);
const allowedIds = new Set(ALLOWED.map((entry) => entry.id));
const unexpected = blocking.filter((advisory) => !allowedIds.has(advisory.id));
const waived = blocking.filter((advisory) => allowedIds.has(advisory.id));

for (const advisory of waived) {
  const entry = ALLOWED.find((candidate) => candidate.id === advisory.id);
  console.log(`aceptada  ${advisory.id} (${advisory.severity}) ${advisory.package}`);
  console.log(`          ${entry.reason}`);
  console.log(`          se retira cuando: ${entry.removeWhen}`);
}

const stale = ALLOWED.filter((entry) => !blocking.some((advisory) => advisory.id === entry.id));
for (const entry of stale) {
  console.log(`obsoleta  ${entry.id} ya no aparece en el audit: borrar de ALLOWED.`);
}

if (unexpected.length > 0) {
  console.error(`\n${unexpected.length} vulnerabilidad(es) high/critical sin revisar:\n`);
  for (const advisory of unexpected) {
    console.error(`  ${advisory.id}  ${advisory.severity}  ${advisory.package}`);
    console.error(`    ${advisory.title}`);
    console.error(`    ${advisory.url}`);
  }
  console.error("\nActualizar la dependencia o, si no aplica, documentarla en ALLOWED.");
  process.exit(1);
}

const counts = report.metadata?.vulnerabilities ?? {};
console.log(
  `\nOK: sin vulnerabilidades high/critical pendientes ` +
    `(moderate: ${counts.moderate ?? 0}, low: ${counts.low ?? 0}).`
);
