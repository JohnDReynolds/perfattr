# perfattr Roadmap 3: Subsequent Feature Backlog

**Status:** Noncommitted backlog as of September 4, 2026.

This document records possible work after roadmap 2. It is ordered primarily by
technical dependency, not by promised delivery. Nothing here authorizes implementation
or a public API change. An item must first be specified, approved, and promoted into an
active roadmap.

## Promotion rules

Before promoting a feature:

- state the user problem and why existing contracts do not already solve it;
- define the methodology, inputs, outputs, null behavior, and reconciliation identities;
- identify any result-schema or compatibility change;
- verify primary references, licensing, and intellectual-property considerations;
- construct independent hand-calculated fixtures; and
- define proportionate correctness and performance gates before implementation.

Prefer one small policy or methodology at a time. Add a general abstraction only when
two implemented cases demonstrate the need.

When designing relevant features, review
[`pybrinson`](https://github.com/gghez/pybrinson/) for useful ideas about methodology
boundaries, public APIs, invariants, fixtures, hierarchy, and linking. Treat it as a
comparative design reference rather than the calculation authority: verify formulas
against primary sources, make independent design decisions for `perfattr`, and complete
the required license and fixture-provenance review before reusing code or test data.

## 1. Harden supported modeling conventions

These items are substantially representable by the existing authoritative-contribution
contract. Start with documentation and fixtures; add calculation behavior only if a
real gap remains.

### Explicit cash

- Document cash as an attributable identifier rather than a hidden residual.
- Test positive, negative, and zero cash weights and their reconciliation behavior.
- Leave decisions about identifying or synthesizing cash to host accounting adapters.

### Fees and financing

- Document authoritative contribution with zero weight and an undefined return.
- Preserve nonzero contribution rather than forcing weight-times-return reconstruction.
- Add semantic labels only outside stable numerical result schemas unless a later
  methodology requires them.

### Derivative exposure

- Require the host adapter to supply the selected exposure basis.
- Do not infer market value, notional, delta-adjusted exposure, or another convention.
- Record exposure-basis provenance without making it an attribution effect.

## 2. Add time-aware classification

### Effective-dated classifications

- Resolve classification assignments for each source period before consolidation.
- Define overlap, gap, boundary-date, and missing-assignment behavior.
- Permit portfolio and benchmark to use different source identifiers and mappings.
- Reconcile results when an identifier changes classification inside a reporting
  period.

Roadmap 2 establishes the required pipeline order but does not commit this feature.

### Multi-level hierarchical roll-up

- Support a classification tree of arbitrary documented depth.
- Define leaf, parent, root, missing-parent, and cycle behavior.
- Ensure child effects reconcile exactly to every reported parent.
- Keep hierarchy metadata separate from numerical identifiers and presentation labels.

Candidate methodological reference: Bacon (2008), chapter 5. Verify the exact edition
and applicable formulas during specification.

## 3. Add explicit single-period methodology policies

### Separate interaction effect

- Preserve the initial policy in which portfolio-weighted selection absorbs
  interaction.
- Add an explicit policy that reports interaction separately.
- Do not silently reinterpret the released selection column.
- Approve a result-schema compatibility plan before adding an interaction column.

### Brinson-Fachler three-effect attribution

- Add allocation, selection, and interaction as distinct effects.
- Retain the existing Brinson-Fachler allocation convention as the baseline.
- Make the selected methodology and interaction convention explicit in results and
  reconciliation evidence.

Candidate methodological reference: Brinson and Fachler (1985).

### Brinson-Hood-Beebower three-effect attribution

- Add the BHB allocation convention with separate selection and interaction.
- Share validated infrastructure with Brinson-Fachler without obscuring the different
  financial formulas.
- Require independent fixtures that make the BF and BHB allocation difference visible.

Candidate methodological reference: Brinson, Hood, and Beebower (1986).

## 4. Add linking methods one at a time

The current baseline already includes logarithmic contribution linking and Carino
active-effect linking. Reconcile the term "Cariño log-smoothing" with the implemented
baseline before proposing additional Carino work.

When the first additional method is promoted, introduce one explicit linking-method
policy rather than a general plugin framework. Preserve each method's period effects,
full-horizon effects, and reconciliation identities.

Suggested evaluation order:

1. **Frongello recursive linking** — candidate reference: Frongello (2002).
2. **GRAP factor linking** — candidate reference: GRAP (1997).
3. **Geometric linking** — candidate reference: Bacon (2008), chapter 6.
4. **Menchero optimized linking** — candidate references: Menchero (2000, 2004).

The order may change after the specifications expose complexity or user value. Verify
the exact publications, formulas, and intellectual-property status—particularly for
Menchero—before implementation.

## 5. Add external-flow reconciliation evidence

- Keep flow-adjusted return measurement in the host accounting layer.
- Define an optional reconciliation input that discloses external-flow components.
- Do not silently classify flows as allocation, selection, interaction, or residual
  attribution effects.
- Add this only when the evidence improves an actual audit workflow without burdening
  ordinary weights-and-returns users.

## 6. Add currency attribution as a separate calculation family

- Specify required local, currency, and base-currency returns before adding columns.
- Define portfolio and benchmark currency exposures, hedging conventions, and
  reconciliation identities explicitly.
- Keep currency attribution separate from the existing domestic Brinson result schema.
- Reuse general validation or linking helpers only where the financial meaning remains
  identical.

Candidate methodology: Karnosky-Singer four-effect additive currency attribution.
Candidate reference: Karnosky and Singer (1994). Verify the primary methodology and
input requirements during specification.

## Deliberately deferred architecture

This backlog does not justify a plugin system, universal attribution engine, generic
method graph, or speculative columns. Calculation policies, schema variants, and shared
abstractions should emerge only from approved, independently tested implementations.
