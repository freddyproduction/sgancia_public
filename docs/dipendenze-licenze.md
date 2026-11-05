# Dipendenze e licenze — inventario

Rilevato il 4 novembre 2026 dai metadati dell’immagine runtime e dal lockfile npm. È un inventario tecnico, non un parere legale né una garanzia di compatibilità. Le licenze devono essere controllate anche nei testi distribuiti dai pacchetti prima della release stabile.

## Backend runtime (include strumenti Python di base)

| Pacchetto | Versione | Licenza dichiarata |
|---|---|---|
| alembic | 1.20.1 | MIT |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.16.0 | MIT |
| argon2-cffi | 25.1.0 | MIT |
| argon2-cffi-bindings | 26.1.0 | MIT |
| cbor2 | 6.2.0.post2 | MIT |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| fastapi | 0.162.0 | MIT |
| greenlet | 3.5.6 | MIT AND PSF-2.0 |
| h11 | 0.16.0 | MIT |
| httptools | 0.9.0 | MIT |
| idna | 3.20 | BSD-3-Clause |
| Mako | 1.4.3 | MIT |
| MarkupSafe | 3.0.4 | BSD-3-Clause |
| opentelemetry-api | 1.45.2 | Apache-2.0 |
| pillow | 13.0.0 | MIT-CMU |
| pip | 26.2.2 | MIT |
| psycopg | 3.3.6 | LGPL-3.0-only |
| psycopg-binary | 3.3.6 | LGPL-3.0-only |
| pyasn1 | 0.6.5 | BSD-2-Clause |
| pyasn1_modules | 0.4.2 | BSD |
| pycparser | 3.12 | BSD-3-Clause |
| pydantic | 2.14.2 | MIT |
| pydantic-settings | 2.16.2 | MIT |
| pydantic_core | 2.50.2 | MIT |
| pyOpenSSL | 26.4.0 | Apache License, Version 2.0 |
| PyOTP | 2.10.0 | MIT |
| pypdf | 6.21.4 | BSD-3-Clause |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| PyYAML | 6.0.3 | MIT |
| reportlab | 5.1.0 | BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc. |
| SQLAlchemy | 2.0.55 | MIT |
| starlette | 1.10.0 | BSD-3-Clause |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| uvicorn | 0.54.0 | BSD-3-Clause |
| uvloop | 0.23.0 | MIT License |
| watchfiles | 1.3.0 | MIT |
| webauthn | 3.0.1 | BSD-3-Clause |
| websockets | 17.4 | BSD-3-Clause |

## Frontend e strumenti build/test

| Pacchetto | Versione | Licenza dichiarata |
|---|---|---|
| @axe-core/playwright | 4.11.0 | MPL-2.0 |
| @babel/code-frame | 7.29.7 | MIT |
| @babel/compat-data | 7.29.7 | MIT |
| @babel/core | 7.29.7 | MIT |
| @babel/generator | 7.29.12 | MIT |
| @babel/helper-compilation-targets | 7.29.7 | MIT |
| @babel/helper-globals | 7.29.7 | MIT |
| @babel/helper-module-imports | 7.29.7 | MIT |
| @babel/helper-module-transforms | 7.29.7 | MIT |
| @babel/helper-plugin-utils | 7.29.7 | MIT |
| @babel/helper-string-parser | 7.29.11 | MIT |
| @babel/helper-validator-identifier | 7.29.7 | MIT |
| @babel/helper-validator-option | 7.29.7 | MIT |
| @babel/helpers | 7.29.10 | MIT |
| @babel/parser | 7.29.12 | MIT |
| @babel/plugin-transform-react-jsx-self | 7.29.7 | MIT |
| @babel/plugin-transform-react-jsx-source | 7.29.7 | MIT |
| @babel/template | 7.29.7 | MIT |
| @babel/traverse | 7.29.12 | MIT |
| @babel/types | 7.29.11 | MIT |
| @esbuild/aix-ppc64 | 0.28.2 | MIT |
| @esbuild/android-arm | 0.28.2 | MIT |
| @esbuild/android-arm64 | 0.28.2 | MIT |
| @esbuild/android-x64 | 0.28.2 | MIT |
| @esbuild/darwin-arm64 | 0.28.2 | MIT |
| @esbuild/darwin-x64 | 0.28.2 | MIT |
| @esbuild/freebsd-arm64 | 0.28.2 | MIT |
| @esbuild/freebsd-x64 | 0.28.2 | MIT |
| @esbuild/linux-arm | 0.28.2 | MIT |
| @esbuild/linux-arm64 | 0.28.2 | MIT |
| @esbuild/linux-ia32 | 0.28.2 | MIT |
| @esbuild/linux-loong64 | 0.28.2 | MIT |
| @esbuild/linux-mips64el | 0.28.2 | MIT |
| @esbuild/linux-ppc64 | 0.28.2 | MIT |
| @esbuild/linux-riscv64 | 0.28.2 | MIT |
| @esbuild/linux-s390x | 0.28.2 | MIT |
| @esbuild/linux-x64 | 0.28.2 | MIT |
| @esbuild/netbsd-arm64 | 0.28.2 | MIT |
| @esbuild/netbsd-x64 | 0.28.2 | MIT |
| @esbuild/openbsd-arm64 | 0.28.2 | MIT |
| @esbuild/openbsd-x64 | 0.28.2 | MIT |
| @esbuild/openharmony-arm64 | 0.28.2 | MIT |
| @esbuild/sunos-x64 | 0.28.2 | MIT |
| @esbuild/win32-arm64 | 0.28.2 | MIT |
| @esbuild/win32-ia32 | 0.28.2 | MIT |
| @esbuild/win32-x64 | 0.28.2 | MIT |
| @jridgewell/gen-mapping | 0.3.13 | MIT |
| @jridgewell/remapping | 2.3.5 | MIT |
| @jridgewell/resolve-uri | 3.1.2 | MIT |
| @jridgewell/sourcemap-codec | 1.6.0 | MIT |
| @jridgewell/trace-mapping | 0.3.31 | MIT |
| @napi-rs/lzma-linux-x64-gnu | 1.5.1 | MIT |
| @rolldown/pluginutils | 1.0.0-rc.3 | MIT |
| @rollup/rollup-android-arm-eabi | 4.67.4 | MIT |
| @rollup/rollup-android-arm64 | 4.67.4 | MIT |
| @rollup/rollup-android-x64 | 4.67.4 | MIT |
| @rollup/rollup-darwin-arm64 | 4.67.4 | MIT |
| @rollup/rollup-darwin-x64 | 4.67.4 | MIT |
| @rollup/rollup-freebsd-arm64 | 4.67.4 | MIT |
| @rollup/rollup-freebsd-x64 | 4.67.4 | MIT |
| @rollup/rollup-linux-arm-gnueabihf | 4.67.4 | MIT |
| @rollup/rollup-linux-arm-musleabihf | 4.67.4 | MIT |
| @rollup/rollup-linux-arm64-gnu | 4.67.4 | MIT |
| @rollup/rollup-linux-arm64-musl | 4.67.4 | MIT |
| @rollup/rollup-linux-loong64-gnu | 4.67.4 | MIT |
| @rollup/rollup-linux-loong64-musl | 4.67.4 | MIT |
| @rollup/rollup-linux-ppc64-gnu | 4.67.4 | MIT |
| @rollup/rollup-linux-ppc64-musl | 4.67.4 | MIT |
| @rollup/rollup-linux-riscv64-gnu | 4.67.4 | MIT |
| @rollup/rollup-linux-riscv64-musl | 4.67.4 | MIT |
| @rollup/rollup-linux-s390x-gnu | 4.67.4 | MIT |
| @rollup/rollup-linux-x64-gnu | 4.67.4 | MIT |
| @rollup/rollup-linux-x64-musl | 4.67.4 | MIT |
| @rollup/rollup-openbsd-x64 | 4.67.4 | MIT |
| @rollup/rollup-openharmony-arm64 | 4.67.4 | MIT |
| @rollup/rollup-win32-arm64-msvc | 4.67.4 | MIT |
| @rollup/rollup-win32-ia32-msvc | 4.67.4 | MIT |
| @rollup/rollup-win32-x64-gnu | 4.67.4 | MIT |
| @rollup/rollup-win32-x64-msvc | 4.67.4 | MIT |
| @standard-schema/spec | 1.1.0 | MIT |
| @types/babel__core | 7.20.5 | MIT |
| @types/babel__generator | 7.27.0 | MIT |
| @types/babel__template | 7.4.4 | MIT |
| @types/babel__traverse | 7.28.0 | MIT |
| @types/chai | 5.2.3 | MIT |
| @types/deep-eql | 4.0.2 | MIT |
| @types/estree | 1.0.10 | MIT |
| @types/react | 19.3.0 | MIT |
| @types/react-dom | 19.3.0 | MIT |
| @vitejs/plugin-react | 5.2.0 | MIT |
| @vitest/expect | 4.1.12 | MIT |
| @vitest/mocker | 4.1.12 | MIT |
| @vitest/pretty-format | 4.1.12 | MIT |
| @vitest/runner | 4.1.12 | MIT |
| @vitest/snapshot | 4.1.12 | MIT |
| @vitest/spy | 4.1.12 | MIT |
| @vitest/utils | 4.1.12 | MIT |
| assertion-error | 2.0.1 | MIT |
| axe-core | 4.11.4 | MPL-2.0 |
| baseline-browser-mapping | 2.11.34 | Apache-2.0 |
| browserslist | 4.29.5 | MIT |
| caniuse-lite | 1.0.30001820 | CC-BY-4.0 |
| chai | 6.3.0 | MIT |
| convert-source-map | 2.0.0 | MIT |
| csstype | 3.2.3 | MIT |
| debug | 4.4.3 | MIT |
| electron-to-chromium | 1.5.472 | ISC |
| es-module-lexer | 2.3.2 | MIT |
| esbuild | 0.28.2 | MIT |
| escalade | 3.2.0 | MIT |
| estree-walker | 3.0.3 | MIT |
| expect-type | 1.4.0 | Apache-2.0 |
| fdir | 6.5.0 | MIT |
| fsevents | 2.3.3 | MIT |
| gensync | 1.0.0-beta.2 | MIT |
| js-tokens | 4.0.0 | MIT |
| jsesc | 3.1.0 | MIT |
| json5 | 2.2.3 | MIT |
| lru-cache | 5.1.1 | ISC |
| lucide-react | 0.577.0 | ISC |
| magic-string | 0.30.21 | MIT |
| ms | 2.1.3 | MIT |
| nanoid | 3.3.20 | MIT |
| node-releases | 2.0.63 | MIT |
| obug | 2.2.1 | MIT |
| pathe | 2.0.3 | MIT |
| picocolors | 1.1.1 | ISC |
| picomatch | 4.0.7 | MIT |
| playwright | 1.56.1 | Apache-2.0 |
| playwright-core | 1.64.1 | Apache-2.0 |
| fsevents | 2.3.2 | MIT |
| playwright-core | 1.56.1 | Apache-2.0 |
| postcss | 8.5.32 | MIT |
| react | 19.3.1 | MIT |
| react-dom | 19.3.1 | MIT |
| react-refresh | 0.18.0 | MIT |
| rollup | 4.67.4 | MIT |
| scheduler | 0.28.0 | MIT |
| semver | 6.3.1 | ISC |
| siginfo | 2.0.0 | ISC |
| source-map-js | 1.2.2 | BSD-3-Clause |
| stackback | 0.0.2 | MIT |
| std-env | 4.3.0 | MIT |
| tinybench | 2.9.0 | MIT |
| tinyexec | 1.3.1 | MIT |
| tinyglobby | 0.2.17 | MIT |
| tinyrainbow | 3.2.0 | MIT |
| typescript | 5.9.3 | Apache-2.0 |
| update-browserslist-db | 1.3.4 | MIT |
| vite | 7.3.7 | MIT |
| vitest | 4.1.12 | MIT |
| why-is-node-running | 2.3.0 | MIT |
| yallist | 3.1.1 | ISC |

## Controlli vulnerabilità

`npm audit` sul lockfile: 0 vulnerabilità conosciute. `pip-audit` sul requirements.lock runtime: 43 dipendenze, 0 vulnerabilità conosciute. Esito puntuale del 4 novembre 2026: ripetere al rilascio. Nessun pacchetto audit è stato aggiunto all’immagine produzione.

Il progetto è AGPL-3.0-only; Python/PostgreSQL/Node e le immagini base conservano le proprie licenze. Non è ancora attestata una revisione legale completa delle licenze transitive o dei binari nelle immagini: è un requisito aperto della release stabile. Non rimuovere avvisi e testi di terzi durante la distribuzione.

Caricamento archivi dal browser: python-multipart 0.0.33, Apache-2.0, bloccato nei lockfile runtime e test.
