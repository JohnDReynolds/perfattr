# perfattr Documentation

Start with the [user guide](user_guide.md) for installation, an end-to-end preparation
workflow, result selection, and the user-visible edge cases that matter most.

The documents below are normative calculation contracts. Roadmaps record why and how
features were implemented; specifications define their current behavior.

## Core workflow

- [Portable preparation](preparation_specification.md)
- [Arithmetic attribution](specification.md)
- [Effective-dated classifications](effective_dated_classification_specification.md)

## Arithmetic methods and linking

- [Brinson-Fachler three-effect](brinson_fachler_three_effect_specification.md)
- [Brinson-Hood-Beebower three-effect](brinson_hood_beebower_three_effect_specification.md)
- [Brinson-Hood-Beebower two-effect](brinson_hood_beebower_two_effect_specification.md)
- [Frongello recursive linking](frongello_recursive_linking_specification.md)
- [Menchero optimized linking](menchero_optimized_linking_specification.md)

## Separate calculation families

- [Geometric excess-return attribution](geometric_attribution_specification.md)
- [Hierarchical result roll-up](hierarchical_result_rollup_specification.md)
- [Single-period currency attribution](currency_attribution_specification.md)
- [Multi-period currency roll-up](multi_period_currency_rollup_specification.md)

## Engineering evidence

- [Performance method and current observations](performance.md)
- [Feature backlog and decision records](../_extras/perfattr_roadmap_3.md)
- [User-view review](../_extras/userview/2026-09-09_user_experience_review.md)

Public APIs also carry complete type annotations and Google-style docstrings, so
`help(perfattr.prepare_attribution)` and editor tooltips provide concise boundary
documentation without requiring a generated API site.
