# Lanzamiento público — Checklist de GitHub (manual)

> Guía con los clics exactos para configurar el repositorio antes de hacerlo
> **público**. Todo lo que se toca aquí se hace en la web (github.com), sin
> `gh` CLI. Los archivos del repo ya están listos en esta rama.

---

## 0. Preparación (ya hecho en código)

- [x] `README.md` (ES) y `README.EN.md` (EN) con switcher de idioma.
- [x] `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`.
- [x] Templates de issues (Bug report / Feature request) y PR.
- [x] `.github/dependabot.yml` y `.github/social-preview.png`.
- [x] Artefactos personales eliminados del repo (bug-001…008, BOT_KNOWLEDGE,
      config/config.yaml).

---

## 1. Settings generales

Dashboard: `https://github.com/caosssj/Crypto.Bot/settings`

1. **General → Repository name / description** (¡la descripción vende!):
   > `Autonomous memecoin trading bot for Solana. Detects new tokens with
   > DexScreener, scores them with 11 on-chain filters (Helius) + local AI
   > (Qwen3), and executes swaps via Jupiter — with active TP/SL/trailing risk
   > management and a Streamlit dashboard. DRY_RUN by default.`
2. **Website** en el About → dejar **vacío** (sin GitHub Pages).
3. **Social preview** → ya expuesto desde `Settings → Social preview`; el botón
   **"Upload image"** se puede dejar sin subir nada: GitHub usará
   `.github/social-preview.png` del repo automáticamente. Verifícalo en
   `Settings → Social preview` (debe mostrar la vista previa generada).
4. **Features**: activar **Issues**, **Pull requests**, **Discussions** y
   **Projects** (las discusiones ayudan a la comunidad).
5. **Merge button**: desmarcar "Allow merge commits" (opcional); dejar squash y
   rebase.
6. **Automatically delete head branches**: ✅ marcar.

## 2. Topics

En la barra lateral derecha del repo → **About → edit → Topics**:

```
solana  trading-bot  memecoin  dexscreener  jupiter  helius  python
qwen3  streamlit  solana-defi  quantitative-trading  trading
algorithmic-trading  web3
```

## 3. Branch protection (main)

`https://github.com/caosssj/Crypto.Bot/settings/branches`

Crear regla para `main`:

- [x] **Require status checks to pass before merging** → añadir los checks
  bloqueantes de CI: `ruff check`, `black --check`, `test` (o el nombre del job,
  ver `.github/workflows/ci.yml`).
- [x] **Require pull request reviews**: 1 review.
- [x] **Require branches to be up to date**.
- [ ] (Recomendado) **Do not allow bypassing** (hecho: nadie más toca main).

## 4. Releases (crear las 3 versiones desde los tags)

Página: `https://github.com/caosssj/Crypto.Bot/releases/new?target=v2.2`

1. **Crea la de v2.2 como "Latest release"** (la primera, luego las otras):
   - Tag: `v2.2` (target `main`).
   - Título: `v2.2 — CI hardening + docs + QA review`.
   - Notas: botón **"Generate release notes"** y ajustar con las entradas del
     [CHANGELOG.md](../CHANGELOG.md) (CI bloqueante, README/docs reescritos,
     revisión crítica de QA, tags anotados).
   - Marcar **"Set as the latest release"**.
2. Repetir para `v2.1` → `Backfill v2.1 — persistencia, dashboard y ejecución
   real` (sin marcar latest).
3. Repetir para `v2.0` → `v2.0 — primera versión funcional` (sin marcar latest).
4. Opcional: adjuntar las capturas `docs/assets/dashboard.png` y
   `docs/assets/cli-report.png` como imágenes del body.

> Nota: tras crear la Release `v2.2`, sustituir en ambos README el badge estático
> `version-2.2` por el dinámico:
> `https://img.shields.io/github/v/release/caosssj/Crypto.Bot?color=blue&label=release`.

## 5. Discussions (comunidad)

`https://github.com/caosssj/Crypto.Bot/discussions`

1. Con la pestaña **Discussions** activada (Settings → Features), crear
   categorías: `Show and tell`, `Ideas`, `¿Preguntas/Questions?` y `Q&A`.
2. Configurar en **Settings → Discussions**: la expectativa de respuesta.
3. Poner una **discusión de bienvenida** en `Show and tell` (mini-intro del README
   y capturas del dashboard).

## 6. Seguridad

`https://github.com/caosssj/Crypto.Bot/security`

- [ ] **Security advisories**: revisar la política de [SECURITY.md](../SECURITY.md).
- [ ] Activar **Dependabot alerts** en `Settings → Code security and analysis`.

## 7. Antes de pulsar "Make public"

1. Confirmar en `Settings → Danger Zone` qué email/apps quedan visibles (revisar
   perfil para no exponer datos personales involuntarios).
2. `git fetch origin && git status` en local: nada sin subir.
3. Hacer un "final read" del README en el navegador (escritorio + móvil).
4. Pulsar **Change visibility → Make public** (el repo es parte del plan del
   usuario; asegúrate de ser tú quien lo hace).

---

## Autorrellenar las plantas

Al final, repasar el About:

- **Description**: la del punto 1.
- **Topics**: los del punto 2.
- **Social preview**: la imagen `.github/social-preview.png`.
- **Links/Websites**: vacío (sin Pages).

---

**Fuente de metadatos honestos:** versiones reales (tags v2.0/v2.1/v2.2),
cobertura real (67 %), tests reales (130) y disclaimer real (riesgo total). No
añadir ningún claim que no esté verificado en el código.