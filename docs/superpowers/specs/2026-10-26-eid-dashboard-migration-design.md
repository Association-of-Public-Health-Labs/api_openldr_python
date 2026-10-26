# EID (DPI) Dashboard Migration: Design

**Date:** 2026-10-26
**Model:** the VL migration, `2026-10-12-vl-dashboard-migration-design.md`, and the `openldr-dashboard` skill.

## 1. Goal

Replace the legacy EID dashboard at https://dpi.openldr.org.mz with a new app, `apps/eid` ("Portal de DPI"), in the monorepo next to VL and TB. Its data comes from `api_openldr_python` (`/hiv/eid/...`) instead of the legacy TypeScript API (`openldr-api`, api-ts.openldr.org.mz).

Why: VL, TB and EID become one platform:
- the same shell, sign-in and dashboard switcher
- one API that is checked, cached and documented

The legacy Next 12 app and the legacy API can then be retired.

### Decisions taken (by the user)

| Topic | Decision |
|---|---|
| Sign-in | **Required** (Clerk, same as VL/TB). Today's dashboard is public. |
| Pages | **Same structure as VL:** Sumário, Laboratório, Província/Distrito/US, Pacientes (admins only), Transporte |
| Address | Launch at **eid.openldr.org.mz**. Later move **dpi.openldr.org.mz** to it (cutover) |
| Name | **Portal de DPI** |
| Colour | **#fda92d** |
| Backend | `api_openldr_python` only. Nothing new in `openldr-api`. |
| Users and roles | One user base and **single sign-on** across all dashboards. The admin role is shared (§6.1). |
| Results | **`FinalResult`** is the definitive result (✱7). |
| Pacientes | Include contacts: the caregiver's phone and the mother's PTV identifiers (§4.5). |

### Calls made in this design (not yet confirmed by the user)

1. **Province detail page.** The legacy `/province/[province]` page becomes a drill-down on the Sumário map: clicking a province shows its districts and a facility indicators table (§5.2). There is no separate page.
2. **Legacy bugs.** These are fixed and marked ✱ (§4.4).
3. **Export format.** Excel export replaces the legacy CSV "Exportar Dados". "Baixar Gráfico" becomes the standard "Exportar imagem".
4. **Card titles** keep the legacy wording. The menu spelling "Provincia" becomes "Província/Distrito/US", as in VL.
5. **Dropped features:**
   - The legacy `/eid` duplicate page; its 2 extra cards move into Sumário.
   - The empty `/rotas` and `/patients` pages.
   - The guided tour, the English locale, the "Contraste" setting and the `/info/v.1.0.0` page.
6. **Same rules as VL:**
   - **Admin role:** from the API probe (§5.1).
   - **Card filters:** each card keeps its own filters; there is no global filter.

### Out of scope

- COVID or other modules.
- Rewriting the legacy app.
- New indicators beyond the legacy cards. The exceptions are Pacientes and Transporte, which the user asked for.
- Switching dpi.openldr.org.mz is piece 3b, done only after the user signs off.

## 2. Current state (verified 2026-10-26)

### Legacy UI: `openldr-dashboard` (Coolify "EID Nextjs Dashboard", branch `main`)

- **Stack:** Next 12 Pages Router, MUI 5, ApexCharts and chart.js.
- **Data loading:** pages are ISR and load the last 12 months on the server. Each card then refetches on its own when its filter changes.
- **Auth:** Auth0, used only for the "Dúvidas e Sugestões" email. There is no page gating.
- **Menu:** "Sumário" `/`, "Lab" `/lab`, "Província" `/clinic`.
- **Inventory:** 28 live cards: 6 on `/`, 10 on `/lab`, 12 on `/clinic`. There are 2 more on the hidden `/eid` page, and the province page has 3 blocks.
- **Card chrome:** the menu has Editar (filter popup), Exportar Dados (CSV), Baixar Gráfico (PNG), Reiniciar o relatório, Ver a Documentação (MDX) and Dúvidas e Sugestões.
- **Filter popups:**
  - `national`: dates only.
  - `lab`: dates + labs, conventional or PoC.
  - `facility`: dates + type (province/district/clinic) + facilities.
- **Requests:** the browser calls `BACKEND_API` directly with `dates[0]/dates[1]`, `labCodes[]`, `facilityCodes[]` (names, not codes), `facilityType`, `category` and `disaggregation`.

Full card inventory, with exact titles, fields and endpoints: Appendix A.

### Legacy API: `openldr-api` (Coolify "openldr-api-ts")

- **Routes:** 42 EID routes (`/eid/lab` 15, `/eid/dash` 13, `/eid/clinic` 14) with **no authentication**.
- **Data:** Sequelize on `EIDData.dbo.EIDMaster`, which was rebuilt on 2026-10-19 (129 columns, no `Result*` duplicates, new `PCR_Result`/`POC_Result`/`FinalResult`). PR #15 fixed the routes for the new schema, and they all return 200.
- **Rules the API pieces must reproduce:** Appendix B.

### Python API: `hiv/eid` (37 routes, on `dev` and `master`)

- **Broken in production.** Every lab, facility and summary route fails with `Invalid column name 'Result…'`. The queries and model use `Result*`-prefixed columns, which the rebuilt EIDMaster no longer has. This was checked live on 2026-10-26 with a signed-in token.
- **Wrong status codes.** Errors come back as **HTTP 200** with the raw SQL error in the body, because `_execute_eid_service` is used instead of `run_reporting_endpoint`.
- **Missing features:**
  - no report cache and no EID cache seeds
  - no `lab_code` filter
  - no rejection reasons
  - no POC positivity from `POC_Result`
  - equipment compares the bucket name instead of the analyser codes
  - no TAT quality filters
  - no monthly summary indicators
  - no patients routes
- **Positivity text is inconsistent:** `%Positive%` (English) in most routes, `Positivo` in others.
- **Auth is already right:** `authenticate_request` verifies the signature, the same as VL, so no piece 0 is needed.
- **Tests only mock the service.** There are no SQL-compile tests and no parity script.
- **Transport routes already work:** `transport/tat_by_location/` and `tat_by_week/` (ReportData `EIDTransportTATPerWeek`) use the shared pipeline.

**Conclusion:** the EID API is a rewrite of the lab, facility and summary services against the new schema, not a parity patch.

## 3. Pieces and order

| Piece | Repo | Content | Merge |
|---|---|---|---|
| 0 | platform | **Single sign-on** (§6.1): Clerk production instance on `openldr.org.mz`, shared by VL, TB and EID | before 3b |
| 1a | API | Schema fix + shared pipeline + shared EID counting rules + SQL-compile tests | → `dev` |
| 1b | API | Endpoints for every card (§4.3), patients (§4.5), parity script, cache seeds, docs | → `dev`, one PR per page group |
| 2 | monorepo | Move generic VL code to packages (§5.0), then `apps/eid` page by page, hidden until reviewed | → `main` (one PR per page or two) |
| 3a | both | Release API (`dev` → `master`, manual prod deploy), Coolify app, DNS eid.openldr.org.mz, user sign-off | |
| 3b | both | Cutover: dpi.openldr.org.mz → new app, retire the legacy app and API | after sign-off |

A page can be built once its endpoints are on `dev`. Piece 2 can start with the shared-code move while piece 1 is in progress.

## 4. Pieces 1a/1b: EID API (`api_openldr_python/hiv/eid`)

### 4.1 Changes that apply to every EID route

| Item | Change |
|---|---|
| Schema | **First task.** Confirm the `dpi` bind's columns (`INFORMATION_SCHEMA.COLUMNS` for `EIDMaster`) and the result values (`SELECT DISTINCT FinalResult` with counts, plus `PCR_Result`, `POC_Result` for the parity explanation). The user runs the queries. Rewrite `eid_master_model.py` and every query to use the un-prefixed columns: `AnalysisDateTime`, `RegisteredDateTime`, `RequestingProvinceName`, `TestingFacilityName`, `LIMSAnalyzerCode`, `RequestingFacilityLatitude`, … |
| Pipeline | Lab, facility and summary controllers go through `run_reporting_endpoint`: real HTTP status, no exception text, `InvalidParameter` → 400, report cache. Delete `_execute_eid_service` and the stray `print()` in `summary_samples_positivity`. |
| Params | `interval_dates` through `coerce_interval_dates`, with an **inclusive** end date. Case-insensitive truthy `disaggregation`. `lab_type` = `all` / `conventional` / `poc`. New **`lab_code`** list = `TestingFacilityCode IN (...)`. On the registered and rejected lab routes, which group by the receiving lab, it filters `ReceivingFacilityCode` instead (my call: filter on the column the card groups by). `category` for the TAT segment, 0–5, where 0 = collection → hub reception. |
| Location filters | `province[]`, `district[]`, `health_facility[]`, `facility_type`, as in VL. Exclude rows with a null or `'null'` `RequestingProvinceName` when no location filter is given (legacy behaviour). |
| Keys | Keep the snake_case Python names; the frontend adapts. Add `total` wherever it is missing. |
| Docs | The Swagger description of every route states its counting rule and any ✱. The API `CLAUDE.md` gets an EID section. |

### 4.2 Shared EID counting rules (one helper each, in `hiv/eid/services/rules.py`)

**Parity principle (builder: apply it everywhere).** Each rewritten route reproduces the exact rule of the legacy route it replaces (Appendix A gives the mapping). That covers:
- the date column it filters and groups on
- what counts as tested, rejected and pending
- the result patterns
- the exclusions

The only intended differences are the ✱ items in §4.4. Anything else the parity script finds is a bug. Where a helper below is shared, it takes parameters so each route can keep its legacy variant.

**Date columns, per legacy convention:**
- Summary indicators, `indicators_by_province`, registered and rejected: `RegisteredDateTime`. Tested and pending are counted inside that registration group.
- Tested, gender, positivity, TAT and equipment: `AnalysisDateTime`.
- `key_indicators`: `AnalysisDateTime` in the window OR `RegisteredDateTime` in the window.

Each SQL-compile test asserts its route's column.

The table below summarises the legacy rules. Where it disagrees with the legacy code, the legacy code wins.

| Measure | Rule |
|---|---|
| Conventional / PoC | Conventional = `IsPoc = 'No'` AND `LIMSAnalyzerCode NOT IN ('MPIMA','PIMA')`. PoC = `IsPoc = 'Yes'` OR `LIMSAnalyzerCode IN ('MPIMA','PIMA')`. ✱ The legacy summary indicators split PCR/PoC by `RequestID` digits; they now use this rule too. The parity script reports the difference. |
| Tested | `AnalysisDateTime IS NOT NULL`. The routes whose legacy version also excluded rejected rows (for example `lab/all/samples_tested_by_month`) keep that exclusion. |
| Positive / negative / indeterminate | ✱7 **`FinalResult`** is the definitive result for every sample, for both conventional and PoC (user decision, 2026-10-26). One helper `result_class()` maps its values to positive / negative / indeterminate; the mapping comes from `SELECT DISTINCT FinalResult`. This replaces the legacy patterns: `'%Pos%'`, `'Pos%'`, `= 'Positivo'`, PCR OR POC, and PoC `Detec%`. |
| Rejected | `LIMSRejectionCode` OR `LIMSRejectionDesc` non-empty, on `RegisteredDateTime` (legacy). `key_indicators` keeps its legacy `HL7ResultStatusCode = 'X'`. |
| Rejection reasons | The legacy 9 buckets: Repetir Teste (REPIT, SPUN2, REJOL); Amostra Insuficiente (INS, UNS); Requisição Sem Amostra (RSA, NSRP, SDBSA); Problemas Técnicos (ERRTC, ACC, PROBT, PRTLA); Sangue Sobreposto (SASOB); Registo Duplicado (DUPRG); Amostra Mal Identificada (NAME); Amostra com +30 dias de Colheita (AM30D); Outros Motivos (everything else). Keys: `repeat_test, insufficient_sample, request_without_sample, technical_problems, overlapping_blood, duplicate_registration, misidentified_sample, sample_over_30_days, other`. |
| Pending | Not rejected AND `FinalResult` empty (✱7). The legacy treated `PCR_Result IN ('NDT','Nível de detecção baixo')` as pending too; check where those values end up in `FinalResult` with the distinct-values query, and keep them pending if they appear there. |
| TAT segments | Six `AVG(DATEDIFF(day, …))` values: `collection_hub_reception`, `hub_reception_hub_registration`, `hub_registration_lab_reception`, `lab_reception_lab_registration`, `lab_registration_analysis`, `analysis_validation`. Legacy quality filters: hub dates in order; lab reception within 0–90 days of hub registration; analysis within 30 days of registration; `TestingFacilityCode NOT IN ('PBC','PEM','UEM')`; conventional only; 0 counted as 1. |
| TAT brackets | `lt_7`, `between_7_15`, `between_16_21`, `gt_21`, `no_dates`, for the chosen `category` segment, with the same filters. |
| Equipment | `LIMSAnalyzerCode` groups: CAPCTM (ALINA, AL-IM, ALINB, ALIND, ALINK); ALINITY (ALNTA, ALNTY); M2000 (M2000, M200A, M200B); C6800 (C6800, C6800A, C6800B); PANTHER (PNTHA, PNTHR); MPIMA (MPIMA, PIMA); MANUAL (MANUA, MGIT, SYSMX, ''). `HL7ResultStatusCode = 'F'`, conventional, not `PBC`. Returns `tested` + the 7 groups. |
| Sex | `HL7SexCode` F / M. |

### 4.3 Endpoints by page

Rows marked "change" rewrite an existing route; "new" rows add one. "Monthly" responses carry `year, month, month_name`. "By level" responses carry `requesting_facility` plus the drill level, following `facility_type` and `disaggregation` as in VL.

**Sumário** (`summary/`)

| Card | Endpoint | Returns |
|---|---|---|
| KPI tiles + Principais Indicadores (conventional/PoC tabs) | change `summary/indicators/` → monthly, with `lab_type` | `registered, tested, rejected, pending` per month (tiles = sums) |
| Positividade das Amostras | change `summary/positivity/` → monthly | `tested, positive, negative, indeterminate`, `conventional_positive, poc_positive`. ✱ The line becomes positive ÷ tested |
| Amostras por Província (map) + drill | change `summary/indicators_by_province/` | `province, registered, tested, rejected, pending, conventional, poc, positive, positivity` |
| Map drill: district and facility table | change `facilities/key_indicators/` (by level, `lab_type`) | `requesting_facility, registered, tested, rejected, pending, positive, positivity` |
| Tempo de Resposta por mês | change `summary/tat/` (TAT rule) | monthly + 6 segments |
| TRL – <segmento> | change `summary/tat_samples/` → monthly, `category` | monthly + brackets |
| Amostras Rejeitadas/Mês | change `summary/rejected_samples_by_month/` | monthly + 9 reasons + `total` |
| Amostras Testadas por Equipamento | change `summary/samples_by_equipment_by_month/` | monthly + `tested` + 7 groups |

**Laboratório** (`laboratories/`, all with `lab_code`)

| Card | Endpoint | Returns |
|---|---|---|
| Amostras Testadas por lab/Convencional, …/PoC (+ drill lab → province → district → facility) | change `laboratories/tested_samples/` (`lab_type`, `facility_type=lab\|province\|district\|health_facility`) | group column, `total, positive, negative` |
| Amostras Testadas/Mês (Todos/Convencional/PoC) | change `laboratories/tested_samples_by_month/` | monthly `total, positive, negative` |
| Amostras Registadas/Mês | change `laboratories/registered_samples_by_month/` (lab = `ReceivingFacilityCode`, legacy) | monthly `total, conventional, poc` |
| TRL – <segmento> (per lab) | change `laboratories/tat_samples/` → per lab, `category` | `testing_facility` + brackets |
| Tempo de Resposta (Convencional) (+ drill) | change `laboratories/tat/` (`facility_type` regrouping) | group column + 6 segments |
| Amostras Testadas por Equipamento (monthly / per lab) | change `samples_by_equipment_by_month/`, `samples_by_equipment/` | `tested` + 7 groups |
| Amostras Rejeitadas/Mês, Amostras Rejeitadas por Lab | change `rejected_samples_by_month/`, `rejected_samples/` (lab = receiving facility, legacy) | 9 reasons + `total`. ✱ The lab filter now applies (the legacy card sent the wrong parameter) |

**Província/Distrito/US** (`facilities/`, by level with drill)

| Card | Endpoint | Returns |
|---|---|---|
| Amostras Registadas/Província, /Mês | change `registered_samples/`, `registered_samples_by_month/` | `conventional, poc, total` |
| Amostras Testadas/Província, /Mês (Todos/PoC/Convencional) | change `tested_samples/`, `tested_samples_by_month/` (`lab_type`) | `conventional, poc, total, positive, negative` |
| Amostras Rejeitadas/Província, /Mês | change `rejected_samples/`, `rejected_samples_by_month/` | 9 reasons + `total` |
| Amostras Testadas por Sexo/Província, /Mês – <categoria> | change `tested_samples_by_gender/`, `tested_samples_by_gender_by_month/` (`lab_type`) | `male_positive, male_negative, female_positive, female_negative` |
| Tempo de Resposta por província (média), por Mês (média) | change `tat_avg/`, `tat_avg_by_month/` | 6 segments |
| Tempo de Resposta por Província (em dias), por Mês (em dias) | change `tat_days/`, `tat_days_by_month/` (`category`, brackets incl. `no_dates`) | brackets |

`facilities/tested_samples_by_age/` stays, but no card uses it (follow-up). The `laboratories/sample_routes*` routes are not used by any card; they are left as they are.

### 4.4 Legacy bugs fixed (✱)

1. Province page: the conventional rows were a copy of the PoC rows (both called `/clinic/poc/key_indicators`). Each lab type now gets its own data.
2. The lab rejection cards sent `facilities` instead of `labCodes`, so the lab filter was ignored. It now applies.
3. "Positividade das Amostras" plotted conventional ÷ total. It now plots positive ÷ tested.
4. PoC positivity was read from `PCR_Result` in the legacy lab routes. It is now covered by ✱7.
5. Date windows cut the last day at 00:00. The end date is now inclusive.
6. PCR/PoC split by `RequestID` digits on the summary. It now uses the lab-type rule.
7. Results (positivity, pending, the patient's result) come from `FinalResult`, the definitive result, instead of the legacy `PCR_Result`/`POC_Result` patterns. The parity script lists positivity and pending differences as expected ✱7 and reports their size.

Each ✱ is noted in the card's docs ("Notas") and in Swagger.

### 4.5 Patients (`hiv/eid/patients/*`, new)

- **Routes:** `by_facility`, `by_name` and `by_result_type`, mirroring `hiv/vl/patients/*`. Admin-only, bound parameters only, `per_page` ≤ 500.
- **Fields:**
  - `request_id`, `name` (masked in the UI as in TB/VL)
  - `sex`, `age_in_days` / age group
  - `requesting_province`, `requesting_district`, `requesting_facility`, `testing_facility`
  - `specimen_date`, `registered_date`, `analysis_date`, `authorised_date`
  - `lab_type`, `result` (`FinalResult`, ✱7), `rejection_reason`
  - **Contacts (user decision, 2026-10-26: include them):**
    - `caregiver_phone` (`CaregiverMobileContact`)
    - the mother's PTV identifiers (`PtvMother` and related fields)

  Confirm the exact column names in the schema query. These are third-party contact details, so they are returned only by these admin-only routes, never written to logs, and included in the patients Excel export only for admins, as in VL.
- **Filters:** `province`, `district`, `health_facility`, `lab_code`, `lab_type`, `result_type` (positive/negative/indeterminate/rejected/pending), and the date window.
- **Admin probe:** the app uses `/hiv/eid/patients/by_facility/?per_page=1`.

### 4.6 Tests, parity, cache

- **SQL-compile tests** (mssql dialect) for every service. Assert:
  - the date column
  - un-prefixed columns only (a test fails if any `Result`-prefixed column is used)
  - the lab-type rule
  - the result columns per lab type
  - the rejection buckets
  - the TAT filters and brackets
  - the equipment groups
  - the `lab_code` filter
  - the inclusive end date
- **`tools/eid_parity_check.py`**, modelled on `vl_parity_check.py`:
  - Covers every legacy route used by a card (Appendix A).
  - Translates the parameters: `dates[]`, `labCodes`, `facilityType`, `facilityCodes`.
  - Compares legacy api-ts.openldr.org.mz (public) with Python dev, using a token, over one closed 12-month window and one 3-month window.
  - Normalises keys and aggregates where the shapes differ.
  - **Acceptance:** zero unexpected differences; every expected difference is a listed ✱.
- **Cache seeds:** add the default 12-month request of every card to `tools/report_cache_seeds.py`.

## 5. Piece 2: `apps/eid` (openldr-monorepo)

### 5.0 Shared code first

Generic code currently inside `apps/vl` moves to `packages/` before EID uses it. VL's tests must pass unchanged.
- Visual code goes to `design_system`.
- Non-visual code goes to `utilities`.

Files to move:
- `hooks/use-report.ts`, `use-facility-report.ts`
- `components/report-card.tsx`, `card-message.tsx`, `lab-report-card.tsx`, `facility-report-card.tsx`, `patients-dialog.tsx`, `charts/*`
- `lib/vl/request-gate.ts`, `dates.ts`, `format.ts`, `geo.ts`, `drill.ts`, `export/*`
- the generic parts of `transport/` (map, TAT classes, weekly trend)

The VL-specific parts stay in VL. Where a moved file has VL assumptions (`VL_BASE`, the lab list), they become parameters.

### 5.1 Shell

- Copied from `apps/vl` per the skill's scaffold guide: `<html data-dashboard="eid">`, `PlatformThemeProvider dashboard="eid"`, Clerk `middleware.ts`, `config/api.ts`, Dockerfile.
- **Dashboard registry** (`dashboards.ts`):
  - `id: "eid"`, `name: "Diagnóstico Precoce Infantil"`, `portalTitle: "Portal de DPI"`
  - `url: "https://eid.openldr.org.mz"`, `primary: "#fda92d"`, `ready: false`
  - `NEXT_PUBLIC_DASHBOARD_URL_EID`
- **Theme:** `theme.css` gets a `[data-dashboard="eid"]` block. Foreground colour: choose the one with the best contrast on #fda92d (probably `#1C252E`; check AA).
- **`lib/eid/`:**
  - `api.ts`: `EID_BASE = "/hiv/eid"`
  - `types.ts`, `series.ts`: EID colours (positive/negative, conventional/PoC, 9 reasons, 7 equipment groups)
  - `labs.ts`: conventional labs and PoC sites, with codes. The source is the dictionary API; check the shared `LabDialog` against what `lab_code` needs (VL ruling P2).
  - `nav.ts` with `UNRELEASED_PAGES`, and the admin probe (§4.5)
- **Navigation:** Sumário `/`, Laboratório `/lab`, Província/Distrito/US `/clinic`, Pacientes `/patients` (admins only), Transporte `/transport`.

### 5.2 Pages

Every card uses the VL card folder: `constants.ts`, `actions.ts`, `actions.test.ts`, `docs.tsx` and a thin `index.tsx`.

- **Card names:**
  - Folder names: `eid-<name>`.
  - Titles: the legacy titles from Appendix A.
  - Docs: rewritten from the legacy MDX into `CardDocs`, with the ✱ notes.
- **Sumário:**
  - KPI tiles (Total, Registadas, Testadas, Rejeitadas, each with % of registered).
  - Positividade das Amostras.
  - Amostras por Província: a map with VL-style drill. Clicking a province shows its districts, a facility indicators table with a conventional/PoC tab, and the province's KPI tiles. This replaces `/province/[x]`.
  - Tempo de Resposta por mês; TRL – <segmento>; Principais Indicadores (conventional/PoC tabs); Amostras Rejeitadas/Mês; Amostras Testadas por Equipamento.
- **Laboratório:** the 10 legacy lab cards.
  - The filter is dates + labs, with a conventional/PoC choice. It uses `lab_code` (VL `LabReportCard` pattern).
  - Drill-down cards go lab → province → district → facility.
  - A "Tipo de Teste" select (Todos/Convencional/PoC) where the legacy card had one.
- **Província/Distrito/US:** the 12 legacy cards, using the VL `FacilityReportCard` drill (province → district → facility → patients for admins). Category selects (lab type or TAT segment) sit in the card, like the TB tabs.
- **Pacientes:** VL's patients page with EID fields and filters. Names are masked.
- **Transporte:** VL's transport page, generalised in §5.0, fed by `/hiv/eid/transport/*`. It shows "Colheita à recepção no laboratório" with the same TAT classes.

### 5.3 Behaviour

The same rules as VL:
- **Default period:** the last 12 months, with the year in month labels.
- **States:** skeleton on first load; Portuguese error message with "Tentar novamente"; empty message.
- **Reset:** "Reiniciar o relatório".
- **Exports:** Excel with title and period; transparent map image.
- **Drill-down:** rows with no name are grouped as "Sem …"; "Dúvidas e Sugestões" uses the shared `MainCard` flow.

### 5.4 Build and test

- `pnpm --filter=eid test`, `exec tsc --noEmit`, `lint`, and `pnpm turbo run build --filter=eid --filter=vl --filter=tb`.
- Before a page leaves `UNRELEASED_PAGES`, it passes the skill's data review checklist against dev and production data. That includes legacy parity on the same window.

## 6. Piece 3: Deploy and cutover

### 6.1 Piece 0: single sign-on for all dashboards (user decision, 2026-10-26)

**The rule:** all dashboards share the same users and one sign-in. A user signed in on VL is signed in on EID and TB too. The admin role is shared as well: an admin is an admin on every dashboard.

**Today:** the apps use Clerk's **development** instance, which keeps one session per subdomain. Signing in on vl.openldr.org.mz does not sign the user in on tb.openldr.org.mz.

**Needed:**
1. The user creates a Clerk **production** instance for `openldr.org.mz`; Claude cannot do it.
2. Add Clerk's DNS records.
3. Set the production keys (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` at build time, `CLERK_SECRET_KEY`) on every dashboard app.
4. Set the API's `CLERK_ISSUER` / `CLERK_JWTS_URL` (production and dev APIs).
5. Move the existing users over (Clerk export/import).
6. Check that the role lookup in `openldr_api_user_users` still matches users after the move.

**Constraint:** this is its own project, with its own plan. It touches VL and TB in production. It must be finished before the dpi.openldr.org.mz cutover (3b), so that current EID users get one account that works everywhere.

Follow the skill's `deploy-guide.md`.

**3a, release:**
1. API `dev` → `master` release PR. The user merges it, adds the variables, and the production API is deployed manually.
2. DNS A record `eid`.
3. Coolify app "EID Dashboard":
   - Dockerfile `/apps/eid/Dockerfile`, base `/`, port 3000
   - watch paths `apps/eid/**`, `packages/**`, the lockfile
   - health check `/sign-in`
   - variables: the 6 VL variables, with `NEXT_PUBLIC_*` set at build time
4. Verify, then set `ready: true`.

**3b, cutover** (after the user signs off on each card):
1. Piece 0 (single sign-on) is done. Create accounts on the shared Clerk production instance for current EID users who don't have one (the user provides the list), and announce the change: sign-in is new for them.
2. Lower the TTL.
3. Point dpi.openldr.org.mz at the new app (both domains on the Coolify app). Write the rollback down first: the old Coolify app stays stopped but deployable.
4. Stop the legacy app.
5. Retire the legacy EID API after a grace period. Check first that nothing else calls `/eid` on api-ts.

## 7. Risks

- **Result values.** Positivity changes source (✱7). The `FinalResult` value mapping must be settled from real data before any rule is written, and the size of the shift against the legacy must be shown to the user before release.
- **Sign-in is new for EID users.** Clerk accounts must exist before the cutover, or users are locked out. The announcement explains the change.
- **Lab-type rule change on the summary (✱6)** can shift PCR/PoC numbers. The parity script quantifies the shift, and the card docs explain it.
- **Facility names.** The legacy app filters by facility *names* (`facilityCodes`). The Python API uses province/district names plus `health_facility`. Names with accents must match the map keys (accent-insensitive `geo.ts`).
- **API load.** About 30 more default requests. The report cache and warm-up seeds are needed before the release; gunicorn has only 3 workers.
- **Shared-code move** touches VL in production. VL's tests stay unchanged and must pass, and VL is smoke-tested after each move.

## 8. Follow-ups (not in this work)

- An age-group card (`tested_samples_by_age` exists).
- Sample routes map (`laboratories/sample_routes*`).
- Retiring `openldr-api` entirely; other modules may still use it.
- A Clerk production instance (the shared dev instance is a known follow-up for all dashboards).

## Appendix A: legacy card inventory

Source: `openldr-dashboard/reports/eid/*`. "→" gives the legacy endpoint (`/eid/...`).

**Sumário (`/`)**
1. KPI tiles: Total de Amostras, Amostras Registadas, Amostras Testadas, Amostras Rejeitadas → `dash/pcr/indicators` + `dash/poc/indicators`
2. Positividade das Amostras (columns Total, line %) → `dash/samples_positivity`
3. Amostras por Província (map, conventional/PoC legend; click → `/province/<name>`) → `dash/indicators_by_province`
4. Tempo de Resposta por mês (em dias) (6 segments) → `dash/pcr/tat`
5. TRL – <segmento> (brackets per month, segment select) → `dash/pcr/tat_samples`
6. Principais Indicadores das Amostras (table by month, conventional/PoC tabs) → `dash/pcr|poc/indicators`
7. Amostras Rejeitadas/Mês (9 reasons; hidden `/eid` page) → `dash/rejected_samples_monthly`
8. Amostras Testadas por Equipamento (hidden `/eid` page) → `dash/samples_by_equipment_monthly`

**Laboratório (`/lab`)**
1. Amostras Testadas por lab/Convencional (Negativo/Positivo; drill lab → province → district → clinic) → `lab/conventional/samples_tested`
2. Amostras Testadas por lab/PoC (drill) → `lab/poc/samples_tested`
3. Amostras Testadas/Mês (Convencional/PoC select) → `lab/all/samples_tested_by_month`
4. TRL – <segmento> (per lab) → `lab/tat_samples`
5. Tempo de Resposta (Convencional) (6 segments by lab; drill) → `lab/conventional/tat`
6. Amostras Registadas/Mês (Convencional/PoC) → `lab/all/samples_registered_by_month`
7. Amostras Testadas por Equipamento → `lab/samples_by_equipment_monthly`
8. Amostras Testadas por Equipamento (Lab) → `lab/samples_by_equipment`
9. Amostras Rejeitadas/Mês (9 reasons) → `lab/rejected_samples_monthly`
10. Amostras Rejeitadas por Lab (9 reasons) → `lab/rejected_samples`

**Província/Distrito/US (`/clinic`)** (all drill province → district → clinic)
1. Amostras Registadas/Província (Convencional/POC) → `clinic/samples_registered_province`
2. Amostras Registadas/Mês → `clinic/samples_registered_month`
3. Amostras Testadas/Província → `clinic/samples_tested_province`
4. Amostras Testadas/Mês (Todos/Poc/Convencional) → `clinic/samples_tested_month`
5. Amostras Rejeitadas/Província (9 reasons) → `clinic/samples_rejected_by_facility`
6. Amostras Rejeitadas/Mês → `clinic/samples_rejected_by_month`
7. Amostras Testadas por Sexo/Província – <categoria> (M/F × Pos/Neg) → `clinic/samples_tested_gender_province`
8. Amostras Testadas por Sexo/Mês – <categoria> → `clinic/samples_tested_gender_month`
9. Tempo de Resposta por província (média) → `clinic/samples_tat_avg_province`
10. Tempo de Resposta por Mês (média) → `clinic/samples_tat_avg_month`
11. Tempo de Resposta por Província (em dias) (segment select) → `clinic/samples_tat_days_province`
12. Tempo de Resposta por Mês (em dias) → `clinic/samples_tat_days_month`

**Province page (`/province/[name]`)**
- Tiles: Total, Registadas, Testadas, Convencional, Poc.
- Province table and map → `dash/indicators_by_province`.
- Facility table → `clinic/poc/key_indicators` (called twice: bug ✱1).

## Appendix B: legacy counting rules (openldr-api after PR #15)

- **Positivity:**
  - lab routes: `PCR_Result LIKE '%Pos%'`, plus `OR POC_Result` on "all"
  - dash: `LIKE 'Pos%'`
  - gender: `= 'Positivo'/'Negativo'`
  - PoC dash: `POC_Result LIKE 'Detec%'/'Undetec%'`
- **Lab type:** see §4.2. The dash PCR/PoC split uses `isnumeric(substring(RequestID,7,3))`.
- **Rejected:** `LIMSRejectionCode` non-empty. Key indicators use `HL7ResultStatusCode = 'X'`. Reasons: see §4.2.
- **Pending:** no result, or `PCR_Result IN ('NDT','Nível de detecção baixo')`, and not rejected.
- **TAT:** the 6 segments, with the filters listed in §4.2. The column chain: `SpecimenDateTime` → `LIMSPreReg_ReceivedDateTime` → `LIMSPreReg_RegistrationDateTime` → `ReceivedDateTime` → `RegisteredDateTime` → `AnalysisDateTime` → `AuthorisedDateTime`.
- **Equipment:** see §4.2.
- **Facility level:** `RequestingProvinceName`/`DistrictName`/`FacilityName` by `facilityType` and `disaggregation`; rows with a null name are excluded.
