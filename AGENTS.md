# Project Coding Guidelines

Apply these conventions when modifying or creating code in this project.

## Roadmap Authority

- Treat `_extras/perfattr_roadmap_1.md` and `_extras/perfattr_roadmap_2.md` as completed
  historical context.
- Treat `_extras/perfattr_roadmap_4.md` and
  `docs/effective_dated_classification_specification.md` as the governing roadmap and
  contract for the current effective-dated classification work.
- Treat unpromoted items in `_extras/perfattr_roadmap_3.md` as a noncommitted backlog.
  A roadmap 3 item does not authorize implementation until it is deliberately promoted
  into a new active roadmap.
- Use this file for engineering conduct and any deliberately approved active roadmap
  for product scope, contracts, sequencing, and boundaries. Do not infer new scope
  from the completed roadmaps or noncommitted backlog.
- Keep the reusable calculation core independent from preparation. Portable,
  source-neutral preparation may live in a separate `perfattr` layer as authorized by
  roadmap 2.
- Keep vendor-specific loading and behavior, portfolio accounting, holiday-file
  loading, source-specific reconciliation, and presentation outside `perfattr`.
- Treat every portable preparation implementation added under roadmap 2 as the sole
  permanent authority. After `ppar` integration passes its parity and performance
  gates, remove the superseded `ppar` implementation rather than maintaining two
  engines. An algorithm-free compatibility facade or data-translation adapter may
  remain where required by `ppar`'s public API.

## Model Reasoning Guidance

- Default to GPT-5.6 Sol Medium.
- Before beginning work that would materially benefit from High or Extra High
  reasoning, notify the user and recommend the appropriate level with a one-sentence
  explanation.
- Recommend High for difficult, cross-cutting design, financial logic, debugging, or
  invariant work.
- Recommend Extra High only for exceptionally difficult problems with substantial
  ambiguity or interacting edge cases.
- Do not recommend changing levels for routine implementation.

## Style And Quality

- Follow PEP 8 unless an established project-specific convention intentionally differs.
- Limit lines to 99 characters.
- Keep code free of `pylint`, Pylance, and `pyright` errors and warnings. Treat a
  Pylance diagnostic observed in the supported editor as a release-gate failure even
  when the command-line `pyright` version does not reproduce it.
- Fix the underlying code or type information rather than suppressing diagnostics,
  excluding checked code, or weakening checker settings. If a diagnostic appears to
  be a false positive or would be disproportionately difficult to resolve, explain
  the diagnostic, attempted fixes, alternatives, and tradeoff, then obtain the
  user's explicit approval before adding the narrowest possible suppression.
- Prefer small, behavior-preserving changes unless a broader refactor has clear value.

## Architecture And Dependencies

- Limit runtime dependencies in the reusable core to pandas, NumPy, and the Python
  standard library.
- Never import `ppar` or Polars from the reusable core. `ppar` integration belongs in
  a thin host adapter outside the portable calculation package.
- Keep file and URL access, vendor schemas, portfolio accounting, holiday-file
  loading, charts, HTML, templates, CLI behavior, and report management outside the
  calculation core. Any generic file readers authorized by roadmap 2 belong in a
  separate I/O module and must use source-neutral schemas.
- Calendar arithmetic, reporting-frequency rules, period alignment, consolidation,
  and classification mapping belong in the portable preparation layer, not the
  calculation core.
- Do not mutate caller-supplied DataFrames. Document ownership of returned DataFrames
  without describing an ordinary or frozen dataclass as making them immutable.

## Test-Gate Integrity

- Never raise, relax, disable, or bypass a test, benchmark, warning threshold, failure
  threshold, invariant, or release gate merely because it is failing.
- Treat an unexpected gate failure as evidence of a possible product regression and
  investigate the implementation first.
- Obtain the user's explicit approval before intentionally changing an established
  gate or threshold. State the current value, proposed value, evidence, and tradeoff.
- Never relax a tolerance specified in a test plan without first obtaining the
  user's explicit approval.
- Use direct `perfattr` benchmarks for standalone core changes, including realistic
  selected-input sizes and measurements of both elapsed time and peak memory.
- Keep the 500x `ppar` scale check in the `ppar` integration release-candidate
  workflow. Run it after changes to the adapter or cross-cutting integration,
  reporting, audit, safety-net, or performance behavior.
- Establish performance thresholds only after a correct prototype produces
  repeatable evidence. Once established, treat them as release gates.
- Keep inexpensive financial, conservation, lineage, and explanation-reconciliation
  invariants enabled in production runs. Put redundant full-artifact reparsing or
  similarly expensive independent verification in test and release-candidate checks
  when running it in production would materially degrade performance.
- Build expected results from independently hand-calculated fixtures. Cover the edge
  cases and linking limits named in the roadmap.
- Use `ppar` only as a temporary development oracle for differential testing. Do not
  import it into `perfattr`, derive independent expected values from it, or require it
  in distributed tests.

## Typing And Naming

- Annotate public parameters, public return values, class attributes, and non-obvious
  local variables where annotations improve readability or type checking.
- Avoid unnecessary annotations for obvious local variables.
- Prefix module-level identifiers with `_` when they are intended only for use within
  that module.
- Do not underscore public APIs or intentionally imported package-internal names.

## Public APIs

- Use idiomatic Python conventions at public boundaries.
- Normalize compatibility sentinels and legacy conventions at public boundaries.
- Preserve public behavior unless an API change is explicitly requested.

## Output Schema Stability

- Establish the initial result-frame schemas as part of the prerelease contract.
- After a schema has been released, do not add, remove, rename, reorder, or reinterpret
  columns without explicit approval and an intentional compatibility plan.
- Use stable, neutral `snake_case` column names and deterministic row and column
  ordering in portable result frames.
- Preserve existing `ppar` output schemas at the adapter boundary. Presentation total
  rows remain the host product's responsibility.

## Financial Contracts

- Treat supplied contribution as authoritative; do not assume it can always be
  reconstructed as weight multiplied by return.
- Preserve zero-weight, nonzero-contribution rows and represent their mathematically
  undefined effective returns as null. Use zero only when both weight and contribution
  are zero.
- Use Brinson-Fachler allocation and the initial portfolio-weighted selection
  convention in which selection absorbs interaction, as specified by the roadmap.
- Preserve logarithmic contribution linking, Carino active-effect linking, and all
  financial reconciliation identities defined by the portable specification.
- Require `1e-12` relative and absolute numerical parity at the `ppar` adapter boundary,
  together with identical null placement, ordering, reconciliation outcomes, and
  presentation-precision output. Do not require bit-for-bit floating-point identity.

## Comments And Financial Logic

- Comment non-obvious intent, business rules, financial interpretation, assumptions,
  sign conventions, and important edge cases.
- Give every nontrivial mathematical implementation a docstring that explains its
  financial purpose, formula, assumptions, numerical limits, and important edge cases.
  Cite the governing primary reference when the formula comes from an external
  methodology.
- Give every test case a useful docstring stating the financial behavior or contract it
  proves. For nontrivial mathematics, document the independent hand calculation,
  expected identity, and why the selected values expose the intended behavior.
- Comment material intermediate expected values in mathematical tests so their
  derivation can be audited without consulting the production implementation.
- Avoid comments that simply paraphrase straightforward code.
- Favor explicit names and intermediate variables when they improve financial
  interpretability or auditability.

## Licensing And Fixture Provenance

- Resolve and document the outbound license before reusing or distributing source
  material from another project.
- Record the provenance of fixtures and reference values. Do not copy `ppar` source or
  fixtures into the standalone package unless their license and intended reuse have
  been explicitly verified.

## Release Gate

Before publishing any `perfattr` version, require all of the following:

- a successful source-distribution and wheel build;
- package metadata validation;
- installation into a clean environment;
- a public-import smoke test;
- passing functional calculation and preparation tests; and
- completed outbound-license and fixture-provenance review for any newly introduced
  material.

## Docstrings

Use consistently formatted Google-style docstrings for all public APIs and meaningful
internal classes and functions. Type annotations do not replace behavioral
documentation.

- Modules should include a concise summary and useful context where appropriate.
- Classes should document their purpose and meaningful public instance state using
  `Attributes:`.
- Nontrivial functions and methods should use applicable `Args:`, `Returns:`, and
  `Raises:` sections.
- Constructors should document their arguments either in the class docstring or in
  `__init__`, following a consistent project-wide approach.
- Use `Yields:` instead of `Returns:` for generators.
- Use `Examples:` when a public entry point is not obvious.
- Use `Notes:` for significant formulas, data-shape expectations, assumptions, or
  validation behavior.
- Use `Warnings:` only for genuine misuse risks or significant side effects.
- Use `References:` for financial methodologies or external specifications when
  useful.
- Use `See Also:` only when it meaningfully improves navigation.
- Trivial private helpers may retain concise one-line docstrings.
- When modifying an existing public API, bring its docstring into compliance as part
  of the same change.
