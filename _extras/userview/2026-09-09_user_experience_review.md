# Project User-Experience Review

**Status:** Complete September 9, 2026.

**Reviewed revision:** `08a163f` (`main` and `origin/main`).

**Follow-up:** The repository was made public after the review. The documentation and
metadata portion of UX-001 through UX-007 was implemented locally in the subsequent
user-onboarding pass; runtime behavior and released result schemas remain unchanged.

This review approached `perfattr` as a package user rather than as its implementer. It
examined the public PyPI and GitHub release experience, current README and
specifications, root API, type and help surfaces, representative domestic and currency
workflows, output frames, common errors, and continuous-integration and publication
workflows. No production source, test, configuration, public documentation, schema,
threshold, or release state was changed.

## Bottom line

`perfattr` feels like a serious, unusually auditable calculation engine. It does not
yet feel like a self-service public Python package.

A performance professional or host-application developer who already understands the
required facts will likely trust it. The formulas are not hidden, inputs are validated
strictly, supplied accounting contribution is respected, outputs are deterministic,
and reconciliation evidence accompanies every calculation family. The pandas API is
small enough to learn and deliberately avoids vendor and presentation policy.

A new PyPI user is more likely to experience uncertainty. The ordinary install gives
an older API, the only published project link leads to a private repository, there is
no installation section, the preparation features are not shown as one workflow, and
the first successful domestic example prints a 22-column frame without explaining
which of five result frames answers which question.

The right response is focused documentation and release cleanup. A CLI, reporting
framework, chart layer, fluent API, or general convenience facade would make this
portable engine less clear rather than more usable.

## What users will like

### The financial posture inspires confidence

- Weights and returns are the ordinary input, while accounting-integrated users can
  provide authoritative contribution.
- Cash, fees, financing, signed weights, missing identifiers, and undefined effective
  returns have explicit rules instead of name-based magic.
- Arithmetic, geometric, hierarchical, and currency calculations use separate public
  boundaries when their mathematical identities differ.
- Every tested public calculation either returned passing reconciliation evidence or
  raised before returning a failed result.
- Outputs use explicit names such as `linked_selection_effect` and
  `currency_allocation_log_effect`; users are not left to infer units or scope from a
  generic `effect` column.

### The Python API is disciplined

The root package exposes 12 functions, six result dataclasses, three policy enums,
public error types, and version metadata. All 12 functions have docstrings, complete
parameter annotations, and annotated returns. Keyword-only policy arguments reduce
accidental misuse, and the default domestic path needs only:

```python
prepared = prepare_attribution(portfolio, benchmark)
result = calculate_attribution(prepared.portfolio, prepared.benchmark)
```

The strict enum boundary rejects misspelled policy strings rather than guessing. Error
messages are concrete: a bad weight sum identifies the side, dates, and received sum;
an unprepared calculation reports its missing `quantity_of_days` column. Callers keep
ordinary pandas frames, and public operations do not mutate their inputs.

### Preparation is a real differentiator

The quarterly smoke workflow compounded three monthly portfolio returns of 1%, 2%,
and 3% to 6.1106%, derived the 91-day prepared period, and passed it directly into
attribution. The ability to validate, align, independently map, and consolidate both
sides is more useful than a calculator that assumes perfectly prepared period data.

### Engineering signals are strong

CI exercises Python 3.11 through 3.14, a separate minimum NumPy/pandas lane, the full
test suite, Pylint, Pyright, distribution construction, and a clean-wheel import. The
publication workflow reruns the functional suite, verifies tag/version artifact names,
checks metadata, and smoke-installs the built wheel before trusted publication. The
runtime dependency list remains pandas and NumPy.

## Findings

### UX-001: public installation did not lead to the current product

**Priority:** Resolved September 9, 2026
**Risk:** High user confusion; no calculation defect

As of September 9, 2026, the [default PyPI project][pypi] identifies `0.3.0` as the
current stable release. A clean command confirmed:

```text
python -m pip install perfattr
installed perfattr 0.3.0
```

That package exports 16 root names and lacks the current attribution-method,
effect-linking, hierarchy, geometric, currency, and currency-roll-up APIs. The local
project is `0.12.0a1` with 25 root exports. A clean user receives it only after already
knowing to run:

```text
python -m pip install --pre --upgrade perfattr
installed perfattr 0.12.0a1
```

At the time of the review, the [latest GitHub release][latest-release] was correctly
marked as a prerelease but the repository was private. The user subsequently made it
public, resolving source and issue-tracker access. The subsequent stable `0.12.0`
release resolved the PyPI default, description, documentation-link, and project-URL
gaps recorded here.

Choose and state one release story:

- If the current API remains alpha, add a short Installation and Release Status block
  showing both the stable and `--pre` commands, and provide public documentation even
  if the repository remains private.
- If the current contracts are ready for ordinary users, publish the current feature
  set as a non-prerelease so `pip install perfattr` selects it.

In either case, add useful `Documentation` and `Issues` project URLs and ensure links
rendered on PyPI are absolute public URLs. Making the repository public would solve
all three discovery problems at once if that is the intended project model. Do not
yank or relabel old releases without a separate release-compatibility decision.

### UX-002: the main preparation workflow is discoverable only in pieces

**Priority:** High documentation value
**Risk:** Low; documentation only

The README proves the simplest in-memory preparation and calculation path, and its
currency example is self-contained. It does not connect the headline preparation
features into one task-oriented sequence:

```text
read canonical files
    -> select portfolio codes when needed
    -> load independent mappings
    -> choose date window, Frequency, and caller holidays
    -> prepare and inspect accepted coverage
    -> calculate
    -> select the appropriate result frame
    -> optionally roll up a hierarchy or currency history
```

The exact rules exist, but they are distributed across long normative specifications.
A new user must discover that `Frequency.MONTHLY` is required instead of the string
`"Monthly"`, that performance CSV files have headers while mapping and classification
files do not, and that the calculation accepts prepared rather than raw frames.

Add one short, nonnormative user guide with an end-to-end domestic CSV example. Keep
the README example small, link to the guide, and show only one optional mapping and one
fixed-frequency argument. No new orchestration function is needed: the existing calls
already compose cleanly.

### UX-003: users need a map of the result frames

**Priority:** High documentation value
**Risk:** Low; documentation only

The two-identifier README calculation produced:

| Result | Shape | Natural user question |
| --- | ---: | --- |
| `period_detail` | 2 x 22 | What happened by period and identifier? |
| `period_summary` | 1 x 18 | What happened in each period? |
| `overall_detail` | 2 x 15 | What happened by identifier over the horizon? |
| `cumulative` | 1 x 20 | How did results develop through time? |
| `reconciliation` | 12 x 9 | Which financial identities were verified? |

Those are sensible outputs for an auditable engine, but the README prints the complete
22-column `period_detail` frame. The first success therefore looks much more complex
than the two-effect result the user asked for. Multi-period detail also contains both
unlinked period effects and effects allocated to the complete horizon; that distinction
is financially important and easy to miss.

Add a compact “Which output should I use?” table and make the first example print
`period_summary` or a selected set of detail columns. Explain in a few sentences:

- period effects versus complete-horizon linked effects;
- `overall_detail` versus chronological `cumulative` output;
- why reconciliation is returned even though a failed check raises; and
- that the package returns decimals and data, not percent formatting or presentation
  total rows.

The full schemas should remain in the specifications. A presentation helper or custom
result class is unnecessary.

### UX-004: incomplete final reporting periods disappear too quietly

**Priority:** High because report coverage is financially consequential
**Risk:** Documentation is low risk; changing behavior is compatibility-sensitive

The preparation specification deliberately omits a final fixed-frequency bucket when
both sides contain the same incomplete bucket. A smoke test with complete January and
February data plus March 1–15 requested at monthly frequency returned January and
February only and emitted no warning. Source reconciliation still included March, but
there was no explicit returned row saying that March was omitted.

This policy is defensible for a live reporting feed, but a user can easily believe the
requested history was fully processed. Put the behavior next to the first fixed-
frequency example and tell callers to compare requested/source coverage with the
prepared maximum `thru_date`.

If real users need stronger protection, separately design an explicit strict-
completeness option or returned coverage metadata. Do not silently change the existing
omission rule or warning contract as a documentation cleanup.

### UX-005: mapping and classification behavior can surprise users

**Priority:** Medium
**Risk:** Low for documentation

An identifier absent from a supplied mapping falls back to itself. Mapping only
`Equity` to `Risk Assets` in the smoke input therefore returned identifiers `Bonds`
and `Risk Assets`, mixing an original identifier with a classification bucket. This is
useful for partial mappings but is not the completeness policy many users will assume.

Classification files are also display metadata for a host; their names do not enter
preparation or appear in numerical results. The README currently says classification
readers are available without showing where that metadata goes.

Document both facts in the user guide. Users who require complete mapping should be
shown how to compare source identifiers with mapping identifiers before preparation.
Do not make full coverage mandatory globally; identity fallback is an intentional and
useful contract.

### UX-006: reconciliation is valuable but not uniform across result families

**Priority:** Medium; defer schema changes
**Risk:** High if released frames are changed

The reconciliation concept is consistent, but its physical interfaces are not:

| Family | Shape of evidence |
| --- | --- |
| Preparation | Long rows with `stage`, `side`, `check`, `residual`, and `passed` |
| Arithmetic | Long rows with `scope`, `check`, `residual`, and `passed` |
| Hierarchy | Long rows adding `identifier`, with `residual` and `passed` |
| Geometric | Long rows with `difference` rather than `residual` |
| Currency | One period row with three separate `*_reconciled` flags |
| Currency roll-up | Long rows with `difference` and `passed` |

A host cannot write one generic audit-table consumer across all results. This does not
make any result incorrect, and the family-specific forms are individually readable.
For now, document them in the output guide and let adapters normalize only what their
applications need. Consider a common additive audit view only when a concrete host
requires it; changing released frames requires explicit approval and a compatibility
plan.

### UX-007: a few accepted specifications still sound unfinished

**Priority:** Low but worthwhile
**Risk:** Documentation only

The preparation specification still says effective-dated implementation is incomplete
and that the released preparation API supports only static mappings. Effective-dated
mapping is released. The accepted geometric, hierarchy, and currency specifications
also use plan-language such as “Add a public function” immediately after statuses that
say the feature is implemented and released.

Make current contracts read in the present tense while retaining roadmaps as historical
implementation records. This is a small credibility improvement for a user following
the README's specification links.

## Output assessment

The output design favors auditability over immediate presentation, which is the right
choice for this package. A user gets exact decimal data, stable ordering, explicit
method metadata, identifier detail, time summaries, cumulative views, and evidence of
the identities that were checked. Currency output is especially clear about log-return
units.

The cost is volume. One successful two-leaf hierarchy roll-up created 56 reconciliation
rows, and a two-identifier domestic calculation returned five frames with 87 columns
across their schemas. That is appropriate machine-facing evidence but a poor first
screen. Documentation should teach users to select the one decision frame first and
treat the rest as audit and drill-down data.

No built-in chart, percentage formatter, total row, HTML report, or classification-name
join should be added to solve this. Those remain host presentation responsibilities.

## Recommended sequence

1. **Distribution and installation clarity — Medium reasoning.** Decide stable versus
   prerelease positioning, make a public documentation destination available, add
   installation commands, and update package URLs.
2. **One-page user and output guide — Medium reasoning.** Document the existing
   pipeline, result selection, enums, mapping fallback, classification metadata, and
   fixed-frequency coverage behavior. Adjust the README's first printed output.
3. **Specification tense cleanup — Medium reasoning.** Correct the stale
   effective-dated sentence and replace plan-language in released contracts.
4. **Incomplete-period API decision — High reasoning only if documentation proves
   insufficient.** Any warning, strictness, or metadata change affects established
   behavior and needs focused compatibility design.
5. **Reconciliation unification — High reasoning only after demonstrated host demand.**
   Preserve current schemas unless a common audit consumer justifies a new boundary or
   future breaking change.

The first three items are the 80/20 user-experience work. They improve the package a
user encounters without adding calculation code or weakening its deliberately narrow
architecture.

## Follow-up disposition

The subsequent [Step 1 onboarding pass](2026-09-09_user_onboarding_step_1.md) made
these documentation and metadata changes:

- added installation and explicit stable-versus-prerelease guidance;
- added a task-oriented user guide and documentation index;
- changed the first README result to a focused period summary and added a result-frame
  chooser;
- documented strict enums, source file forms, caller-supplied holidays, accepted
  coverage, incomplete final buckets, mapping fallback, classification metadata,
  linked-effect interpretation, and family-specific reconciliation shapes;
- converted every README documentation link to an absolute public GitHub target;
- added public Documentation, Issues, and Releases package metadata; and
- changed stale future-tense text in released specifications to current contract
  language.

UX-004's possible strict-completeness API and UX-006's possible common reconciliation
boundary remain deliberately deferred. The subsequent
[stable `0.12.0` release](2026-09-09_stable_release_0.12.0.md) made plain
`pip install perfattr` select the current feature set.

## Evidence collected

- The current local README examples and representative domestic, quarterly,
  hierarchical, geometric, currency, and currency-roll-up workflows completed.
- A clean default PyPI install selected `0.3.0`; a clean `--pre --upgrade` selected
  `0.12.0a1` and exposed the current calculation families.
- Common mistakes produced specific `TypeError`, `PreparationError`, or
  `AttributionError` messages without partial output.
- Public API introspection found 12 fully annotated, fully documented functions and
  six result dataclasses in the current package.
- Public release metadata, repository visibility, CI, publication gates, exact result
  schemas, and incomplete-period and partial-mapping behavior were inspected directly.

[latest-release]: https://github.com/JohnDReynolds/perfattr/releases/tag/v0.12.0a1
[pypi]: https://pypi.org/project/perfattr/
